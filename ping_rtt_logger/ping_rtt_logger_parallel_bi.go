package main

import (
	"bufio"
	"fmt"
	"net"
	"os"
	"os/exec"
	"strings"
	"sync"
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
	logFile, err := os.OpenFile("ping_rtt_values_new.log", os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		fmt.Println("Error opening log file:", err)
		return
	}
	defer logFile.Close()

	var logMutex sync.Mutex

	// Process each network combination
	for i := 0; i < len(networks); i++ {
		currentNetwork := networks[i]

		// Intra-network pings with concurrency
		if len(currentNetwork.Nodes) >= 2 {
			fmt.Printf("\n=== Intra-network pings for %s ===\n", currentNetwork.Name)
			logFile.WriteString(fmt.Sprintf("\n=== Intra-network pings for %s ===\n", currentNetwork.Name))

			var wg sync.WaitGroup
			for srcIdx := 0; srcIdx < len(currentNetwork.Nodes); srcIdx++ {
				for dstIdx := 0; dstIdx < len(currentNetwork.Nodes); dstIdx++ {
					if srcIdx == dstIdx {
						continue
					}
					wg.Add(1)
					go func(sIdx, dIdx int) {
						defer wg.Done()
						srcNode := currentNetwork.Nodes[sIdx]
						dstNode := currentNetwork.Nodes[dIdx]
						processPingConcurrent(
							currentNetwork,
							currentNetwork,
							srcNode,
							dstNode,
							logFile,
							&logMutex,
						)
					}(srcIdx, dstIdx)
				}
			}
			wg.Wait()
		}

		// Inter-network pings with concurrency
		for j := 0; j < len(networks); j++ {
			if j == i {
				continue
			}
			targetNetwork := networks[j]
			fmt.Printf("\n=== Inter-network pings %s → %s ===\n", currentNetwork.Name, targetNetwork.Name)
			logFile.WriteString(fmt.Sprintf("\n=== Inter-network pings %s → %s ===\n", currentNetwork.Name, targetNetwork.Name))

			var wg sync.WaitGroup
			for _, srcNode := range currentNetwork.Nodes {
				for _, dstNode := range targetNetwork.Nodes {
					wg.Add(1)
					go func(src, dst string) {
						defer wg.Done()
						processPingConcurrent(
							currentNetwork,
							targetNetwork,
							src,
							dst,
							logFile,
							&logMutex,
						)
					}(srcNode, dstNode)
				}
			}
			wg.Wait()
		}
	}
}

// Rest of the code remains unchanged
func processPingConcurrent(srcNet, dstNet Network, srcNode, dstNode string, logFile *os.File, mutex *sync.Mutex) {
	srcIP := srcNet.IPs[srcNode]
	dstIP := dstNet.IPs[dstNode]

	// Execute ping command
	cmd := exec.Command("docker", "exec", srcNode, "ping", "-c", "5", "-W", "1", dstIP)
	startTime := time.Now()
	out, err := cmd.CombinedOutput()
	duration := time.Since(startTime).Round(time.Millisecond)

	// Parse results
	var avgRTT string
	output := string(out)
	for _, line := range strings.Split(output, "\n") {
		if strings.Contains(line, "rtt min/avg/max/mdev") {
			parts := strings.Fields(line)
			if len(parts) >= 4 {
				stats := strings.Split(parts[3], "/")
				if len(stats) >= 2 {
					avgRTT = fmt.Sprintf("%sms", stats[0])
				}
			}
		}
	}

	// Create log entry
	timestamp := startTime.Format("2006/01/02 15:04:05")
	var logEntry string
	if avgRTT != "" {
		logEntry = fmt.Sprintf("%s [%s] %s (%s) → [%s] %s (%s): %s (test duration: %s)\n",
			timestamp, srcNet.Name, srcNode, srcIP, dstNet.Name, dstNode, dstIP, avgRTT, duration)
	} else {
		errorMsg := "Unknown error"
		if err != nil {
			errorMsg = err.Error()
		}
		logEntry = fmt.Sprintf("%s [%s] %s (%s) → [%s] %s (%s): FAILED - %s\n",
			timestamp, srcNet.Name, srcNode, srcIP, dstNet.Name, dstNode, dstIP, errorMsg)
	}

	// Thread-safe logging
	mutex.Lock()
	defer mutex.Unlock()
	fmt.Print(logEntry)
	logFile.WriteString(logEntry)
}
