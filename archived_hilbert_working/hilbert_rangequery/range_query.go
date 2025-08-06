package main

import (
	"bufio"
	"fmt"
	"log"
	"math"
	"os"
	"sort"
	"strconv"
	"strings"

	"github.com/google/hilbert"
	"github.com/hashicorp/serf/client"
	"github.com/hashicorp/serf/coordinate"
)

const (
	hilbertOrder = 10               // Defines a 1024x1024 grid (2^10)
	rttBuckets   = "5,10,15,20,25,30,35,40,45,50,55,60,65,70,75,80,85" // Comma-separated RTT thresholds in ms
)

// NodeInfo stores a node's network coordinates and Hilbert index
type NodeInfo struct {
	Name       string
	Coord      *coordinate.Coordinate // Serf network coordinates
	HilbertIdx int                    // Precomputed 1D Hilbert index
}

// HilbertSystem manages spatial mapping and query optimization data
type HilbertSystem struct {
	// Spatial mapping parameters
	MinX, MaxX   float64         // Coordinate bounds with padding
	MinY, MaxY   float64
	GridSize     int             // Hilbert curve grid size (2^hilbertOrder)
	SortedNodes  []*NodeInfo     // Nodes sorted by Hilbert index
	curve        *hilbert.Hilbert
	
	// Query optimization data
	LatencyCutoffs map[float64]int // Precomputed cutoffs: [RTT threshold] => max Hilbert difference
}

func main() {
	// Initialize Serf client connection
	serfClient, err := client.ClientFromConfig(&client.Config{Addr: "127.0.0.1:7373"})
	if err != nil {
		log.Fatal("Serf client initialization failed:", err)
	}
	defer serfClient.Close()

	// Get current node name using hostname convention
	currentNode := getCurrentNodeName()
	
	// Fetch node coordinates and create optimized query system
	nodes := getSerfNodes(serfClient)
	hilbertSystem := createHilbertSystem(nodes, currentNode)

	// Start interactive query interface
	runQueryInterface(hilbertSystem, currentNode)
}

// createHilbertSystem initializes spatial mapping and precomputes query data
func createHilbertSystem(nodes map[string]*NodeInfo, referenceNode string) *HilbertSystem {
	system := &HilbertSystem{
		LatencyCutoffs: make(map[float64]int),
	}

	// Step 1: Calculate coordinate bounds with 5% padding
	minX, maxX, minY, maxY := calculateCoordinateBounds(nodes)
	padX, padY := (maxX-minX)*0.05, (maxY-minY)*0.05
	system.MinX = minX - padX
	system.MaxX = maxX + padX
	system.MinY = minY - padY
	system.MaxY = maxY + padY

	// Step 2: Initialize Hilbert curve mapping
	system.GridSize = 1 << hilbertOrder
	curve, err := hilbert.NewHilbert(system.GridSize)
	if err != nil {
		log.Fatal("Hilbert curve creation failed:", err)
	}
	system.curve = curve

	// Step 3: Map all nodes to Hilbert indices
	scaleX := float64(system.GridSize-1) / (system.MaxX - system.MinX)
	scaleY := float64(system.GridSize-1) / (system.MaxY - system.MinY)
	
	for _, node := range nodes {
		// Convert coordinates to grid positions [0, GridSize-1]
		nx := int((node.Coord.Vec[0] - system.MinX) * scaleX)
		ny := int((node.Coord.Vec[1] - system.MinY) * scaleY)
		
		// Clamp to valid grid range
		nx = clamp(nx, 0, system.GridSize-1)
		ny = clamp(ny, 0, system.GridSize-1)
		
		// Calculate Hilbert index
		if idx, err := curve.MapInverse(nx, ny); err == nil {
			node.HilbertIdx = idx
		}
	}

	// Step 4: Sort nodes by Hilbert index for efficient range queries
	system.SortedNodes = make([]*NodeInfo, 0, len(nodes))
	for _, node := range nodes {
		system.SortedNodes = append(system.SortedNodes, node)
	}
	sort.Slice(system.SortedNodes, func(i, j int) bool {
		return system.SortedNodes[i].HilbertIdx < system.SortedNodes[j].HilbertIdx
	})

	// Step 5: Precompute latency cutoffs for reference node
	refNode := nodes[referenceNode]
	precomputeCutoffs(system, refNode, nodes)

	return system
}

// calculateCoordinateBounds finds min/max coordinates across all nodes
func calculateCoordinateBounds(nodes map[string]*NodeInfo) (minX, maxX, minY, maxY float64) {
	minX, maxX = math.MaxFloat64, -math.MaxFloat64
	minY, maxY = math.MaxFloat64, -math.MaxFloat64
	for _, node := range nodes {
		x, y := node.Coord.Vec[0], node.Coord.Vec[1]
		minX, maxX = math.Min(minX, x), math.Max(maxX, x)
		minY, maxY = math.Min(minY, y), math.Max(maxY, y)
	}
	return
}

// precomputeCutoffs implements the exact bucket processing steps
func precomputeCutoffs(system *HilbertSystem, refNode *NodeInfo, nodes map[string]*NodeInfo) {
	// Parse RTT buckets from configuration string
	buckets := parseRTTBuckets()
	
	// Collect RTT and Hilbert difference metrics for all nodes
	type nodeMetric struct {
		rtt         float64
		hilbertDiff int
	}
	var metrics []nodeMetric

	refIdx := refNode.HilbertIdx
	for _, node := range nodes {
		if node.Name == refNode.Name {
			continue // Skip reference node
		}
		
		// Calculate actual RTT using Serf's coordinate model
		rtt := calculateRTT(refNode.Coord, node.Coord)
		
		// Record Hilbert index difference from reference node
		metrics = append(metrics, nodeMetric{
			rtt:         rtt,
			hilbertDiff: abs(refIdx - node.HilbertIdx),
		})
	}

	// Process each latency bucket according to specification
	for _, bucket := range buckets {
		// Step 1: Gather all Hilbert differences for nodes in this bucket
		var diffs []int
		for _, m := range metrics {
			if m.rtt <= bucket {
				diffs = append(diffs, m.hilbertDiff)
			}
		}
		
		if len(diffs) == 0 {
			continue // No nodes in this bucket
		}

		// Step 2: Sort the collected Hilbert differences
		sort.Ints(diffs)

		// Step 3: Calculate 95th percentile cutoff
		percentile := 0.95
		cutoffIndex := int(math.Round(percentile * float64(len(diffs)-1)))
		if cutoffIndex >= len(diffs) {
			cutoffIndex = len(diffs)-1 // Handle edge case
		}
		cutoff := diffs[cutoffIndex]

		// Store cutoff for this bucket
		system.LatencyCutoffs[bucket] = cutoff
		log.Printf("Bucket %.0fms: cutoff=%d (from %d nodes)", bucket, cutoff, len(diffs))
	}
}

// queryNodes implements the final optimized query workflow
func queryNodes(system *HilbertSystem, refNode *NodeInfo, maxRTT float64) []*NodeInfo {
	// Find the largest bucket threshold <= requested RTT
	var bestBucket float64 = -1
	for bucket := range system.LatencyCutoffs {
		if bucket <= maxRTT && bucket > bestBucket {
			bestBucket = bucket
		}
	}
	if bestBucket == -1 {
		return nil // No suitable bucket found
	}

	// Get precomputed cutoff for this bucket
	cutoff := system.LatencyCutoffs[bestBucket]
	refIdx := refNode.HilbertIdx

	// Calculate Hilbert index search range
	minIdx := refIdx - cutoff
	maxIdx := refIdx + cutoff

	// Binary search to find range boundaries in sorted nodes
	left := sort.Search(len(system.SortedNodes), func(i int) bool {
		return system.SortedNodes[i].HilbertIdx >= minIdx
	})
	right := sort.Search(len(system.SortedNodes), func(i int) bool {
		return system.SortedNodes[i].HilbertIdx > maxIdx
	})

	// Final verification with actual RTT calculation
	var results []*NodeInfo
	for _, node := range system.SortedNodes[left:right] {
		if node.Name == refNode.Name {
			continue // Skip reference node
		}
		if calculateRTT(refNode.Coord, node.Coord) <= maxRTT {
			results = append(results, node)
		}
	}

	return results
}

// calculateRTT implements exact Serf RTT calculation including heights and adjustments
func calculateRTT(a, b *coordinate.Coordinate) float64 {
	if len(a.Vec) != len(b.Vec) {
		return math.MaxFloat64
	}

	// Calculate Euclidean distance between coordinates
	sumsq := 0.0
	for i := 0; i < len(a.Vec); i++ {
		diff := a.Vec[i] - b.Vec[i]
		sumsq += diff * diff
	}
	distance := math.Sqrt(sumsq)

	// Apply Vivaldi height model and adjustments
	rtt := distance + a.Height + b.Height
	if adjusted := rtt + a.Adjustment + b.Adjustment; adjusted > 0 {
		rtt = adjusted
	}

	return rtt * 1000 // Convert to milliseconds
}

// Helper functions with improved error handling
func getCurrentNodeName() string {
	hostname, err := os.Hostname()
	if err != nil {
		log.Fatal("Hostname detection failed:", err)
	}
	return fmt.Sprintf("clab-nebula-%s", hostname)
}

func parseRTTBuckets() []float64 {
	var buckets []float64
	for _, s := range strings.Split(rttBuckets, ",") {
		val, err := strconv.ParseFloat(strings.TrimSpace(s), 64)
		if err == nil {
			buckets = append(buckets, val)
		}
	}
	sort.Float64s(buckets)
	return buckets
}

func clamp(val, min, max int) int {
	if val < min {
		return min
	}
	if val > max {
		return max
	}
	return val
}

func abs(x int) int {
	if x < 0 {
		return -x
	}
	return x
}

// getSerfNodes fetches all alive nodes with coordinates
func getSerfNodes(serfClient *client.RPCClient) map[string]*NodeInfo {
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
			continue
		}

		nodes[member.Name] = &NodeInfo{
			Name:  member.Name,
			Coord: coord,
		}
	}

	// Validate reference node exists
	if _, exists := nodes[getCurrentNodeName()]; !exists {
		log.Fatal("Current node not found in Serf members")
	}

	return nodes
}

// findNode locates a node by name in the sorted list
func findNode(nodes []*NodeInfo, name string) *NodeInfo {
	for _, node := range nodes {
		if node.Name == name {
			return node
		}
	}
	return nil
}

// runQueryInterface handles user input and displays results
func runQueryInterface(system *HilbertSystem, currentNode string) {
	reader := bufio.NewReader(os.Stdin)
	for {
		fmt.Print("\nEnter RTT threshold in ms (or 'exit'): ")
		input, _ := reader.ReadString('\n')
		input = strings.TrimSpace(input)

		if input == "exit" {
			break
		}

		rttMs, err := strconv.ParseFloat(input, 64)
		if err != nil {
			fmt.Println("Invalid input")
			continue
		}

		// Execute optimized query
		refNode := findNode(system.SortedNodes, currentNode)
		if refNode == nil {
			log.Fatal("Reference node not found in sorted list")
		}
		results := queryNodes(system, refNode, rttMs)
		printResults(results, currentNode, rttMs)
	}
}

// printResults displays query results with distances
func printResults(results []*NodeInfo, currentNode string, rttMs float64) {
	if len(results) == 0 {
		fmt.Printf("\nNo nodes within %.2fms of %s\n", rttMs, currentNode)
		return
	}

	fmt.Printf("\n=== Nodes within %.2fms of %s ===\n", rttMs, currentNode)
	for i, node := range results {
		// Calculate actual distance for display
		distance := calculateRTT(results[0].Coord, node.Coord)
		fmt.Printf("%3d. %-20s Hilbert: %6d  RTT: %.2fms\n",
			i+1, node.Name, node.HilbertIdx, distance)
	}
}