package main

import (
	"fmt"
	"log"
	"math"
	"os"
	"sort"

	"github.com/google/hilbert"
	"github.com/hashicorp/serf/client"
	"github.com/hashicorp/serf/coordinate"
)

const (
	gridSize = 1024 // Must be power of two
	topN     = 3    // Number of closest nodes to show
)

type NodeInfo struct {
	Name       string
	Coord      *coordinate.Coordinate
	HilbertIdx int
	RTTs       map[string]float64
}

func main() {
	clientConfig := &client.Config{
		Addr: "127.0.0.1:7373",
	}

	serfClient, err := client.ClientFromConfig(clientConfig)
	if err != nil {
		log.Fatalf("Failed to create Serf client: %v", err)
	}
	defer serfClient.Close()

	hostname, err := os.Hostname()
	if err != nil {
		log.Fatalf("Failed to get hostname: %v", err)
	}
	currentNode := fmt.Sprintf("clab-nebula-%s", hostname)

	members, err := serfClient.Members()
	if err != nil {
		log.Fatalf("Failed to get members: %v", err)
	}

	nodes := processNodes(serfClient, members, currentNode)
	mapToHilbert(nodes, gridSize)
	printDuplicateHilbertIndexes(nodes)

	hilbertNeighbors := getHilbertNeighbors(nodes, currentNode, topN)
	rttNeighbors := getRTTNeighbors(nodes, currentNode, topN)
	printResults(currentNode, nodes, hilbertNeighbors, rttNeighbors)
}

func processNodes(serfClient *client.RPCClient, members []client.Member, currentNode string) map[string]*NodeInfo {
	nodes := make(map[string]*NodeInfo)

	for _, member := range members {
		if member.Status != "alive" {
			continue
		}

		coord, err := serfClient.GetCoordinate(member.Name)
		if err != nil || coord == nil {
			continue
		}

		nodes[member.Name] = &NodeInfo{
			Name:  member.Name,
			Coord: coord,
			RTTs:  make(map[string]float64),
		}
	}

	current, exists := nodes[currentNode]
	if !exists {
		log.Fatalf("Current node %s not found in Serf members", currentNode)
	}

	for _, other := range nodes {
		if other.Name != currentNode {
			rtt := calculateRTT(current.Coord, other.Coord)
			current.RTTs[other.Name] = rtt
		}
	}

	return nodes
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
		result = append(result, fmt.Sprintf("%s (%d)", nodeList[i].Name, nodeList[i].HilbertIdx))
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

func printResults(currentNode string, nodes map[string]*NodeInfo, hilbertNeighbors, rttNeighbors []string) {
	fmt.Printf("\n=== Current Node: %s ===\n", currentNode)
	fmt.Printf("Hilbert Index: %d\n", nodes[currentNode].HilbertIdx)

	fmt.Printf("\nTop %d Hilbert Neighbors:\n", topN)
	for i, name := range hilbertNeighbors {
		fmt.Printf("%2d. %s\n", i+1, name)
	}

	fmt.Printf("\nTop %d Serf RTT Neighbors:\n", topN)
	for i, name := range rttNeighbors {
		rtt := nodes[currentNode].RTTs[name]
		fmt.Printf("%2d. %s (%.3f ms)\n", i+1, name, rtt)
	}
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
