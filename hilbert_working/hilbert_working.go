package main

import (
	"bufio"
	"fmt"
	"log"
	"math"
	"net"
	"os"
	"os/exec"
	"regexp"
	"sort"
	"strings"
	"sync"

	"github.com/google/hilbert"
	"github.com/hashicorp/serf/client"
	"github.com/hashicorp/serf/coordinate"
)

const (
	hilbertOrder   = 16 // Generates grid size of 1024 (2^10)
	topN           = 3
	pingCount      = 2
	pingTimeoutSec = 1
	parallelPings  = 20
)

type NodeInfo struct {
	Name       string
	IP         string
	Coord      *coordinate.Coordinate
	HilbertIdx int
	RTTs       map[string]float64
	PingRTTs   map[string]float64
}

type NetworkConfig struct {
	Subnet string
	Nodes  map[string]string
}

func main() {
	networks := loadNetworkConfigs("networks_nodes.txt")

	serfClient, err := client.ClientFromConfig(&client.Config{Addr: "127.0.0.1:7373"})
	if err != nil {
		log.Fatal("Serf client init failed:", err)
	}
	defer serfClient.Close()

	currentNode := getCurrentNodeName()
	log.Printf("Current node: %s", currentNode)

	nodes := processNodes(serfClient, networks, currentNode)
	log.Printf("Processed %d nodes", len(nodes))

	gridSize := 1 << hilbertOrder // Calculate grid size based on order
	mapToHilbert(nodes, gridSize)
	collectPingRTTs(nodes, currentNode)

	printDuplicateHilbertIndexes(nodes)
	printComparisonResults(nodes, currentNode)
}

func loadNetworkConfigs(filename string) map[string]NetworkConfig {
	file, err := os.Open(filename)
	if err != nil {
		log.Fatal("Network config open failed:", err)
	}
	defer file.Close()

	configs := make(map[string]NetworkConfig)
	scanner := bufio.NewScanner(file)

	for scanner.Scan() {
		line := scanner.Text()
		parts := strings.Fields(line)
		if len(parts) < 3 {
			continue
		}

		netName := parts[0]
		subnet := parts[1]
		nodeNames := parts[2:]

		_, ipNet, err := net.ParseCIDR(subnet)
		if err != nil {
			log.Printf("Skipping invalid subnet %s: %v", subnet, err)
			continue
		}

		baseIP := ipNet.IP.To4()
		if baseIP == nil {
			log.Printf("Skipping non-IPv4 subnet %s", subnet)
			continue
		}

		config := NetworkConfig{
			Subnet: subnet,
			Nodes:  make(map[string]string),
		}

		ipCounter := 10
		for _, node := range nodeNames {
			newIP := ipNet.IP.To4()
			newIP[3] = byte(ipCounter)
			config.Nodes[node] = newIP.String()
			ipCounter++
		}

		configs[netName] = config
	}

	return configs
}

func processNodes(serfClient *client.RPCClient, networks map[string]NetworkConfig, currentNode string) map[string]*NodeInfo {
	nodes := make(map[string]*NodeInfo)

	members, err := serfClient.Members()
	if err != nil {
		log.Fatal("Failed to get Serf members:", err)
	}

	for _, member := range members {
		if member.Status != "alive" {
			continue
		}

		coord, err := serfClient.GetCoordinate(member.Name)
		if err != nil || coord == nil {
			log.Printf("Skipping node %s: no coordinate data", member.Name)
			continue
		}

		var ip string
		for _, cfg := range networks {
			if val, exists := cfg.Nodes[member.Name]; exists {
				ip = val
				break
			}
		}

		if ip == "" {
			log.Printf("Warning: No IP found for node %s", member.Name)
			continue
		}

		nodes[member.Name] = &NodeInfo{
			Name:     member.Name,
			IP:       ip,
			Coord:    coord,
			RTTs:     make(map[string]float64),
			PingRTTs: make(map[string]float64),
		}
	}

	current := nodes[currentNode]
	if current == nil {
		log.Fatal("Current node not found in processed nodes")
	}

	for _, other := range nodes {
		if other.Name != currentNode {
			current.RTTs[other.Name] = calculateRTT(current.Coord, other.Coord)
		}
	}

	return nodes
}

func collectPingRTTs(nodes map[string]*NodeInfo, currentNode string) {
	current := nodes[currentNode]
	if current == nil || current.IP == "" {
		log.Fatal("Current node has no IP address")
	}

	log.Printf("Starting ping collection from %s to %d nodes", currentNode, len(nodes)-1)

	type pingJob struct {
		target string
		ip     string
	}

	jobs := make(chan pingJob, len(nodes)-1)
	results := make(chan struct {
		target string
		rtt    float64
	}, len(nodes)-1)

	var wg sync.WaitGroup
	for i := 0; i < parallelPings; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for job := range jobs {
				rtt := pingNode(currentNode, job.ip)
				results <- struct {
					target string
					rtt    float64
				}{job.target, rtt}
			}
		}()
	}

	for name, node := range nodes {
		if name != currentNode && node.IP != "" {
			jobs <- pingJob{name, node.IP}
		}
	}
	close(jobs)

	go func() {
		wg.Wait()
		close(results)
	}()

	successCount := 0
	for res := range results {
		if res.rtt > 0 {
			successCount++
			current.PingRTTs[res.target] = res.rtt
		}
	}
	log.Printf("Completed ping collection. Successful pings: %d/%d", successCount, len(nodes)-1)
}

func pingNode(sourceNode, targetIP string) float64 {
	cmd := exec.Command("ping",
		"-c", fmt.Sprint(pingCount),
		"-W", fmt.Sprint(pingTimeoutSec),
		targetIP,
	)

	output, err := cmd.CombinedOutput()
	if err != nil {
		log.Printf("Ping error from %s to %s: %v", sourceNode, targetIP, err)
		log.Printf("Command output:\n%s", string(output))
		return -1
	}

	rtt := parsePingOutput(string(output))
	if rtt < 0 {
		log.Printf("Failed to parse ping output for %s:\n%s", targetIP, string(output))
	}
	return rtt
}

func parsePingOutput(output string) float64 {
	// Handle different ping output variants
	patterns := []*regexp.Regexp{
		regexp.MustCompile(`(\d+\.\d+)/(\d+\.\d+)/(\d+\.\d+)/(\d+\.\d+)`),   // Linux
		regexp.MustCompile(`= (\d+\.\d+)/(\d+\.\d+)/(\d+\.\d+)/(\d+\.\d+)`), // macOS
	}

	for _, pattern := range patterns {
		matches := pattern.FindStringSubmatch(output)
		if len(matches) >= 3 {
			var avgRtt float64
			_, err := fmt.Sscanf(matches[1], "%f", &avgRtt)
			if err == nil {
				return avgRtt
			}
		}
	}
	return -1
}

// [Keep all other functions unchanged but ensure they exist]

func printComparisonResults(nodes map[string]*NodeInfo, currentNode string) {
	current := nodes[currentNode]

	hilbertNeighbors := getHilbertNeighbors(nodes, currentNode, topN)
	//serfRttNeighbors := getRTTNeighbors(nodes, currentNode, topN)
	pingNeighbors := getPingNeighbors(nodes, currentNode, topN)

	fmt.Printf("\n=== Network Proximity Comparison for %s ===\n", currentNode)
	fmt.Printf("Hilbert Index: %d\n\n", current.HilbertIdx)

	fmt.Printf("Top %d Hilbert Neighbors:\n", topN)
	for i, name := range hilbertNeighbors {
		fmt.Printf(" %d. %s (Index: %d)\n", i+1, name, nodes[name].HilbertIdx)
	}

	// fmt.Printf("\nTop %d Serf RTT Neighbors:\n", topN)
	// for i, name := range serfRttNeighbors {
	// 	fmt.Printf(" %d. %s (%.3f ms)\n", i+1, name, current.RTTs[name])
	// }

	fmt.Printf("\nTop %d Actual Ping Neighbors:\n", topN)
	for i, name := range pingNeighbors {
		fmt.Printf(" %d. %s (%.3f ms)\n", i+1, name, current.PingRTTs[name])
	}
}

func getCurrentNodeName() string {
	hostname, err := os.Hostname()
	if err != nil {
		log.Fatal("Hostname detection failed:", err)
	}
	return fmt.Sprintf("clab-nebula-%s", hostname)
}

func getPingNeighbors(nodes map[string]*NodeInfo, currentNode string, n int) []string {
	current := nodes[currentNode]
	var neighbors []struct {
		name string
		rtt  float64
	}

	for name, rtt := range current.PingRTTs {
		neighbors = append(neighbors, struct {
			name string
			rtt  float64
		}{name, rtt})
	}

	sort.Slice(neighbors, func(i, j int) bool {
		return neighbors[i].rtt < neighbors[j].rtt
	})

	result := make([]string, 0, n)
	for i := 0; i < len(neighbors) && i < n; i++ {
		result = append(result, neighbors[i].name)
	}

	return result
}

func mapToHilbert(nodes map[string]*NodeInfo, gridSize int) {
	minX, maxX := math.MaxFloat64, -math.MaxFloat64
	minY, maxY := math.MaxFloat64, -math.MaxFloat64

	for _, node := range nodes {
		if len(node.Coord.Vec) < 2 {
			continue
		}
		x := node.Coord.Vec[0]
		y := node.Coord.Vec[1]
		if x < minX {
			minX = x
		}
		if x > maxX {
			maxX = x
		}
		if y < minY {
			minY = y
		}
		if y > maxY {
			maxY = y
		}
	}

	h, err := hilbert.NewHilbert(gridSize)
	if err != nil {
		log.Fatalf("Failed to create Hilbert curve: %v", err)
	}

	for _, node := range nodes {
		if len(node.Coord.Vec) < 2 {
			continue
		}

		x := node.Coord.Vec[0]
		y := node.Coord.Vec[1]

		nx := int(((x - minX) / (maxX - minX)) * float64(gridSize-1))
		ny := int(((y - minY) / (maxY - minY)) * float64(gridSize-1))

		idx, err := h.MapInverse(nx, ny)
		if err != nil {
			log.Printf("Failed to map node %s: %v", node.Name, err)
			continue
		}

		node.HilbertIdx = idx
	}
}

func printDuplicateHilbertIndexes(nodes map[string]*NodeInfo) {
	indexMap := make(map[int][]string)

	for _, node := range nodes {
		indexMap[node.HilbertIdx] = append(indexMap[node.HilbertIdx], node.Name)
	}

	fmt.Println("\n=== Duplicate Hilbert Indices ===")
	hasDuplicates := false
	for idx, names := range indexMap {
		if len(names) > 1 {
			hasDuplicates = true
			fmt.Printf("Hilbert Index %d has %d nodes: %v\n", idx, len(names), names)
		}
	}

	if !hasDuplicates {
		fmt.Println("No duplicate Hilbert indices found")
	}
}

func getHilbertNeighbors(nodes map[string]*NodeInfo, currentNode string, n int) []string {
	queryNode := nodes[currentNode]
	var nodeList []*NodeInfo

	for _, node := range nodes {
		if node.Name != currentNode {
			nodeList = append(nodeList, node)
		}
	}

	sort.Slice(nodeList, func(i, j int) bool {
		return abs(nodeList[i].HilbertIdx-queryNode.HilbertIdx) <
			abs(nodeList[j].HilbertIdx-queryNode.HilbertIdx)
	})

	result := make([]string, 0, n)
	for i := 0; i < len(nodeList) && i < n; i++ {
		result = append(result, nodeList[i].Name)
	}

	return result
}

func getRTTNeighbors(nodes map[string]*NodeInfo, currentNode string, n int) []string {
	queryNode := nodes[currentNode]
	type rttNode struct {
		name string
		rtt  float64
	}

	var nodeList []rttNode
	for name, rtt := range queryNode.RTTs {
		nodeList = append(nodeList, rttNode{name, rtt})
	}

	sort.Slice(nodeList, func(i, j int) bool {
		return nodeList[i].rtt < nodeList[j].rtt
	})

	result := make([]string, 0, n)
	for i := 0; i < len(nodeList) && i < n; i++ {
		result = append(result, nodeList[i].name)
	}

	return result
}

func calculateRTT(a, b *coordinate.Coordinate) float64 {
	if len(a.Vec) != len(b.Vec) {
		return math.MaxFloat64
	}

	sumsq := 0.0
	for i := 0; i < len(a.Vec); i++ {
		diff := a.Vec[i] - b.Vec[i]
		sumsq += diff * diff
	}
	rtt := math.Sqrt(sumsq) + a.Height + b.Height

	adjusted := rtt + a.Adjustment + b.Adjustment
	if adjusted > 0.0 {
		rtt = adjusted
	}

	return rtt * 1000
}

func abs(x int) int {
	if x < 0 {
		return -x
	}
	return x
}
