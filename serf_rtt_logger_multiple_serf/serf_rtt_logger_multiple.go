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
	// Open and parse the networks_nodes.txt file.
	file, err := os.Open("networks_nodes.txt")
	if err != nil {
		log.Fatal("Error opening networks_nodes.txt:", err)
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
			log.Printf("Skipping invalid subnet %s: %v", subnet, err)
			continue
		}

		ip = ip.To4()
		if ip == nil {
			log.Printf("Skipping non-IPv4 network %s", subnet)
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
		log.Fatal("Error reading networks_nodes.txt:", err)
	}

	// Open new log file "serf_rtts.log"
	serfLog, err := os.OpenFile("serf_rtts.log", os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
	if err != nil {
		log.Fatal("Error creating serf_rtts.log:", err)
	}
	defer serfLog.Close()

	// Process networks: Intra-network first then Inter-network.
	for currentIdx, currentNet := range networks {
		// Intra-network pings (if at least 2 nodes exist)
		if len(currentNet.Nodes) >= 2 {
			header := fmt.Sprintf("=== Intra-network pings for %s ===\n", currentNet.Name)
			serfLog.WriteString(header)
			fmt.Print(header)
			processIntra(currentNet, serfLog)
			serfLog.WriteString("\n")
			fmt.Print("\n")
		}

		// Inter-network pings: current network to each following network.
		for nextIdx := currentIdx + 1; nextIdx < len(networks); nextIdx++ {
			nextNet := networks[nextIdx]
			header := fmt.Sprintf("=== Inter-network pings %s → %s ===\n", currentNet.Name, nextNet.Name)
			serfLog.WriteString(header)
			fmt.Print(header)
			processInter(currentNet, nextNet, serfLog)
			serfLog.WriteString("\n")
			fmt.Print("\n")
		}
	}
}

// processIntra executes repeated ping tests for each pair within one network.
func processIntra(net Network, logFile *os.File) {
	for i := 0; i < len(net.Nodes); i++ {
		for j := i + 1; j < len(net.Nodes); j++ {
			// Run the serf rtt command 10 times for each node pair.
			execAndLogRepeated(net, net, net.Nodes[i], net.Nodes[j], logFile)
			// Add a blank line as a separator after the 10 tests for this pair.
			logFile.WriteString("\n")
			fmt.Println()
		}
	}
}

// processInter executes repeated ping tests for each node pair between two networks.
func processInter(srcNet, dstNet Network, logFile *os.File) {
	for _, src := range srcNet.Nodes {
		for _, dst := range dstNet.Nodes {
			// Run the serf rtt command 10 times for each node pair.
			execAndLogRepeated(srcNet, dstNet, src, dst, logFile)
			// Add a blank line as a separator after the 10 tests for this pair.
			logFile.WriteString("\n")
			fmt.Println()
		}
	}
}

// execAndLogRepeated runs the serf rtt command 10 times (1 minute interval between runs)
// and logs each result in the specified file.
func execAndLogRepeated(srcNet, dstNet Network, srcNode, dstNode string, logFile *os.File) {
	for attempt := 0; attempt < 10; attempt++ {
		cmd := exec.Command(
			"docker", "exec", srcNode,
			"/opt/serfapp/serf", "rtt", dstNode,
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
		// Write the log entry for this attempt.
		logFile.WriteString(entry + "\n")
		fmt.Println(entry)

		// If not the last attempt, wait 1 minute before the next run.
		if attempt < 9 {
			time.Sleep(1 * time.Minute)
		}
	}
}

// formatResult formats the output of the serf rtt command.
func formatResult(output []byte, err error, duration time.Duration) string {
	if err != nil {
		return fmt.Sprintf("ERROR: %v", err)
	}

	rtt := extractRTT(string(output))
	if rtt < 0 {
		return "INVALID OUTPUT"
	}

	return fmt.Sprintf("%.3fms", rtt) // Removed duration from output
}

// extractRTT extracts the RTT value from the serf output.
// It assumes that the output contains fields and that the 5th field is "rtt:" and the 6th field holds the value.
func extractRTT(output string) float64 {
	parts := strings.Fields(output)
	if len(parts) < 6 || parts[4] != "rtt:" {
		return -1
	}
	var rtt float64
	if _, err := fmt.Sscanf(parts[5], "%f", &rtt); err != nil {
		return -1
	}
	return rtt
}
