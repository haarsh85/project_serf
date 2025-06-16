package main

import (
	"bufio"
	"fmt"
	"log"
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
		log.Fatal("Error opening networks_nodes.txt:", err)
	}
	defer file.Close()

	var networks []Network
	scanner := bufio.NewScanner(file) // Now properly used below

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

		// Uses 'net' import here
		ip, ipNet, err := net.ParseCIDR(subnet)
		if err != nil {
			log.Printf("Skipping invalid subnet %s: %v", subnet, err)
			continue
		}

		ip = ip.To4()
		if ip == nil {
			log.Printf("Skipping non-IPv4 network %s", subnet)
			continue
		}

		baseIP := ip.Mask(ipNet.Mask)
		baseIP[3] = 10

		network := Network{
			Name:   netName,
			Subnet: subnet,
			Nodes:  nodeNames,
			IPs:    make(map[string]string),
		}

		for i, node := range nodeNames {
			nodeIP := make(net.IP, len(baseIP)) // Uses 'net' here
			copy(nodeIP, baseIP)
			nodeIP[3] += byte(i)
			network.IPs[node] = nodeIP.String()
		}

		networks = append(networks, network)
	}

	if err := scanner.Err(); err != nil { // Scanner now properly used
		log.Fatal("Error reading networks_nodes.txt:", err)
	}

	serfLog, err := os.OpenFile("serf_rtt_values.log", os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
	if err != nil {
		log.Fatal("Error creating serf_rtt.log:", err)
	}
	defer serfLog.Close()

	// Process networks in file order
	for currentIdx, currentNet := range networks {
		// Intra-network first if applicable
		if len(currentNet.Nodes) >= 2 {
			header := fmt.Sprintf("=== Intra-network pings for %s ===\n", currentNet.Name)
			serfLog.WriteString(header)
			fmt.Print(header)
			processIntra(currentNet, serfLog)
			// serfLog.WriteString("\n")
			// fmt.Print("\n")
		}

		// Inter-network with all FOLLOWING networks
		for nextIdx := currentIdx + 1; nextIdx < len(networks); nextIdx++ {
			nextNet := networks[nextIdx]
			header := fmt.Sprintf("=== Inter-network pings %s → %s ===\n",
				currentNet.Name, nextNet.Name)
			serfLog.WriteString(header)
			fmt.Print(header)
			processInter(currentNet, nextNet, serfLog)
			// serfLog.WriteString("\n")
			// fmt.Print("\n")
		}
	}
}

func processIntra(net Network, logFile *os.File) {
	for i := 0; i < len(net.Nodes); i++ {
		for j := i + 1; j < len(net.Nodes); j++ {
			src := net.Nodes[i]
			dst := net.Nodes[j]
			execAndLog(net, net, src, dst, logFile)
		}
	}
}

func processInter(srcNet, dstNet Network, logFile *os.File) {
	for _, src := range srcNet.Nodes {
		for _, dst := range dstNet.Nodes {
			execAndLog(srcNet, dstNet, src, dst, logFile)
		}
	}
}

func execAndLog(srcNet, dstNet Network, srcNode, dstNode string, logFile *os.File) {
	cmd := exec.Command(
		"docker", "exec", srcNode,
		"/opt/serfapp/serf_2D", "rtt", dstNode,
	)

	start := time.Now()
	output, err := cmd.CombinedOutput()
	duration := time.Since(start)

	timestamp := start.Format("2006/01/02 15:04:05")
	entry := fmt.Sprintf("%s [%s] %s (%s) → [%s] %s (%s): %s",
		timestamp,
		srcNet.Name, srcNode, srcNet.IPs[srcNode],
		dstNet.Name, dstNode, dstNet.IPs[dstNode],
		formatResult(output, err, duration),
	)

	logFile.WriteString(entry + "\n")
	fmt.Println(entry)
}

func formatResult(output []byte, err error, duration time.Duration) string {
	if err != nil {
		return fmt.Sprintf("ERROR: %v", err)
	}

	rtt := extractRTT(string(output))
	if rtt < 0 {
		return "INVALID OUTPUT"
	}

	return fmt.Sprintf("%.3fms (test duration: %s)", rtt, duration.Round(time.Millisecond))
}

func extractRTT(output string) float64 {
	parts := strings.Fields(output)
	if len(parts) < 5 || parts[4] != "rtt:" {
		return -1
	}
	var rtt float64
	if _, err := fmt.Sscanf(parts[5], "%f", &rtt); err != nil {
		return -1
	}
	return rtt
}
