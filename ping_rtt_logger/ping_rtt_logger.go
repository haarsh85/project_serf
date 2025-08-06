package main

import (
	"bufio"
	"fmt"
	"net"
	"os"
	"os/exec"
	"strings"
	"time"
)

type Network struct {
	Name   string
	Subnet string
	Nodes  []string
	IPs    map[string]string
}

func main() {
	file, err := os.Open("networks_nodes.txt")
	if err != nil {
		fmt.Println("Error opening file:", err)
		return
	}
	defer file.Close()

	var networks []Network
	scanner := bufio.NewScanner(file)

	// Parse network configurations
	for scanner.Scan() {
		line := scanner.Text()
		parts := strings.Fields(line)
		if len(parts) < 3 {
			continue
		}

		netName := parts[0]
		subnet := parts[1]
		nodeNames := parts[2:]

		ip, ipNet, err := net.ParseCIDR(subnet)
		if err != nil {
			fmt.Printf("Invalid subnet: %s\n", subnet)
			continue
		}

		ip = ip.To4()
		if ip == nil {
			fmt.Printf("Non-IPv4 network: %s\n", subnet)
			continue
		}

		baseIP := ip.Mask(ipNet.Mask)
		baseIP[3] = 10 // Starting IP for first node

		network := Network{
			Name:   netName,
			Subnet: subnet,
			Nodes:  nodeNames,
			IPs:    make(map[string]string),
		}

		// Assign IPs to nodes
		for i, node := range nodeNames {
			nodeIP := make(net.IP, len(baseIP))
			copy(nodeIP, baseIP)
			nodeIP[3] += byte(i)
			network.IPs[node] = nodeIP.String()
		}

		networks = append(networks, network)
	}

	if err := scanner.Err(); err != nil {
		fmt.Println("Error reading file:", err)
		return
	}

	// Open log file
	logFile, err := os.OpenFile("ping_rtt.log", os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		fmt.Println("Error opening log file:", err)
		return
	}
	defer logFile.Close()

	// Process each network combination
	for i := 0; i < len(networks); i++ {
		currentNetwork := networks[i]

		// Intra-network pings (only for networks with >= 2 nodes)
		if len(currentNetwork.Nodes) >= 2 {
			fmt.Printf("=== Intra-network pings for %s ===\n", currentNetwork.Name)
			logFile.WriteString(fmt.Sprintf("=== Intra-network pings for %s ===\n", currentNetwork.Name))

			// Generate unique pairs for intra-network
			for srcIdx := 0; srcIdx < len(currentNetwork.Nodes); srcIdx++ {
				for dstIdx := srcIdx + 1; dstIdx < len(currentNetwork.Nodes); dstIdx++ {
					srcNode := currentNetwork.Nodes[srcIdx]
					dstNode := currentNetwork.Nodes[dstIdx]
					processPing(currentNetwork, currentNetwork, srcNode, dstNode, logFile)
				}
			}
		}

		// Inter-network pings to all subsequent networks
		for j := i + 1; j < len(networks); j++ {
			targetNetwork := networks[j]
			fmt.Printf("=== Inter-network pings %s → %s ===\n", currentNetwork.Name, targetNetwork.Name)
			logFile.WriteString(fmt.Sprintf("=== Inter-network pings %s → %s ===\n", currentNetwork.Name, targetNetwork.Name))

			// Ping all nodes in target network
			for _, srcNode := range currentNetwork.Nodes {
				for _, dstNode := range targetNetwork.Nodes {
					processPing(currentNetwork, targetNetwork, srcNode, dstNode, logFile)
				}
			}
		}
	}
}

func processPing(srcNet Network, dstNet Network, srcNode string, dstNode string, logFile *os.File) {
	srcIP := srcNet.IPs[srcNode]
	dstIP := dstNet.IPs[dstNode]

	// 1) Warm-up ping (discard output and errors)
	warmupCmd := exec.Command("docker", "exec", srcNode, "ping", "-c", "1", "-W", "1", dstIP)
	_ = warmupCmd.Run() // ignore errors and output

	// 2) Actual ping measurement (5 pings)
	cmd := exec.Command("docker", "exec", srcNode, "ping", "-c", "5", "-W", "1", dstIP)
	startTime := time.Now()
	out, err := cmd.CombinedOutput()
	duration := time.Since(startTime).Round(time.Millisecond)

	// Parse results
	output := string(out)
	var minRTT string
	lines := strings.Split(output, "\n")
	for _, line := range lines {
		if strings.Contains(line, "rtt min/avg/max/mdev") {
			parts := strings.Fields(line)
			if len(parts) >= 4 {
				stats := strings.Split(parts[3], "/")
				if len(stats) >= 2 {
					minRTT = fmt.Sprintf("%sms", stats[0])
				}
			}
		}
	}

	// Format log entry
	timestamp := startTime.Format("2006/01/02 15:04:05")
	var logEntry string
	if minRTT != "" {
		logEntry = fmt.Sprintf("%s [%s] %s (%s) → [%s] %s (%s): %s (test duration: %s)\n",
			timestamp, srcNet.Name, srcNode, srcIP, dstNet.Name, dstNode, dstIP, minRTT, duration)
	} else {
		errorMsg := "Unknown error"
		if err != nil {
			errorMsg = err.Error()
		}
		logEntry = fmt.Sprintf("%s [%s] %s (%s) → [%s] %s (%s): FAILED - %s\n",
			timestamp, srcNet.Name, srcNode, srcIP, dstNet.Name, dstNode, dstIP, errorMsg)
	}

	// Write output
	fmt.Print(logEntry)
	logFile.WriteString(logEntry)
}
