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
	hilbertOrder = 10 // Defines a 1024x1024 grid (2^10). Higher = more precision but more memory.
)

// NodeInfo stores a node's name, network coordinates, and its position on the Hilbert curve.
type NodeInfo struct {
	Name       string
	Coord      *coordinate.Coordinate // Serf's network coordinates (2D vector)
	HilbertIdx int                    // 1D index on the Hilbert curve (for fast searches)
}

// HilbertMapper manages the mapping between network coordinates and the Hilbert curve.
type HilbertMapper struct {
	MinX, MaxX   float64          // Bounds of the coordinate space (X-axis)
	MinY, MaxY   float64          // Bounds of the coordinate space (Y-axis)
	GridSize     int              // Size of the grid (e.g., 1024 for hilbertOrder=10)
	Sorted       []*NodeInfo      // Nodes sorted by Hilbert index (for binary search)
	curve        *hilbert.Hilbert // Hilbert curve instance
	scaleFactorX float64          // Multiplier to convert X-coords to grid positions
	scaleFactorY float64          // Multiplier to convert Y-coords to grid positions
}

func main() {
	// Initialize Serf client (used to fetch node coordinates)
	serfClient, err := client.ClientFromConfig(&client.Config{Addr: "127.0.0.1:7373"})
	if err != nil {
		log.Fatal("Serf client init failed:", err)
	}
	defer serfClient.Close()

	currentNode := getCurrentNodeName()
	nodes := getSerfNodes(serfClient)    // Fetch all nodes and their coordinates
	mapper := createHilbertMapper(nodes) // Map nodes to the Hilbert curve

	// Interactive prompt for RTT-based searches
	reader := bufio.NewReader(os.Stdin)
	for {
		fmt.Print("\nEnter RTT threshold in ms (or 'exit' to quit): ")
		input, _ := reader.ReadString('\n')
		input = strings.TrimSpace(input)

		if input == "exit" {
			break
		}

		rttMs, err := strconv.ParseFloat(input, 64)
		if err != nil {
			fmt.Println("Invalid input. Please enter a numeric value.")
			continue
		}

		// Convert user's RTT (ms) to coordinate-space units
		rtt := msToCoordinate(rttMs, mapper)
		// Find nodes within the RTT threshold
		results := queryNodesInRTT(nodes[currentNode], rtt, mapper)
		printResults(results, currentNode, rttMs)
	}
}

// Converts milliseconds (real-world time) to coordinate-space distance units.
// This normalizes RTT values to the network's expected maximum latency.
func msToCoordinate(ms float64, mapper *HilbertMapper) float64 {
	maxNetworkRTT := 85.0 // ms (calibrate this to your network's worst-case latency)

	if ms > maxNetworkRTT {
		log.Printf("Warning: RTT %.2fms exceeds design maximum %.2fms", ms, maxNetworkRTT)
	}

	// Scale the RTT proportionally to the coordinate space (e.g., 10ms → 0.117 units)
	return (ms / maxNetworkRTT) * (mapper.MaxX - mapper.MinX)
}

// Fetches all alive Serf nodes and their network coordinates.
func getSerfNodes(serfClient *client.RPCClient) map[string]*NodeInfo {
	nodes := make(map[string]*NodeInfo)

	members, err := serfClient.Members()
	if err != nil {
		log.Fatal("Failed to get Serf members:", err)
	}

	// Filter alive nodes with valid coordinates
	for _, member := range members {
		if member.Status != "alive" {
			continue
		}

		coord, err := serfClient.GetCoordinate(member.Name)
		if err != nil || coord == nil {
			log.Printf("Skipping node %s: no coordinate data", member.Name)
			continue
		}

		nodes[member.Name] = &NodeInfo{
			Name:  member.Name,
			Coord: coord,
		}
	}

	// Ensure current node exists in the list
	if _, exists := nodes[getCurrentNodeName()]; !exists {
		log.Fatal("Current node not found in Serf members")
	}

	return nodes
}

// Creates a Hilbert curve mapper and assigns each node to a position on the curve.
func createHilbertMapper(nodes map[string]*NodeInfo) *HilbertMapper {
	// Step 1: Find the bounds of all node coordinates
	minX, maxX := math.MaxFloat64, -math.MaxFloat64
	minY, maxY := math.MaxFloat64, -math.MaxFloat64
	for _, node := range nodes {
		if len(node.Coord.Vec) < 2 {
			continue
		}
		x := node.Coord.Vec[0]
		y := node.Coord.Vec[1]
		minX = math.Min(minX, x)
		maxX = math.Max(maxX, x)
		minY = math.Min(minY, y)
		maxY = math.Max(maxY, y)
	}

	// Add 5% padding to prevent edge nodes from being clamped to grid boundaries
	padX := (maxX - minX) * 0.05
	padY := (maxY - minY) * 0.05
	minX -= padX
	maxX += padX
	minY -= padY
	maxY += padY

	// Initialize a Hilbert curve with 2^hilbertOrder grid cells (e.g., 1024x1024)
	gridSize := 1 << hilbertOrder
	curve, err := hilbert.NewHilbert(gridSize)
	if err != nil {
		log.Fatalf("Failed to create Hilbert curve: %v", err)
	}

	// Precompute scaling factors to map coordinates to grid cells
	mapper := &HilbertMapper{
		MinX:         minX,
		MaxX:         maxX,
		MinY:         minY,
		MaxY:         maxY,
		GridSize:     gridSize,
		curve:        curve,
		scaleFactorX: float64(gridSize-1) / (maxX - minX), // e.g., 1023 / (coord_range_x)
		scaleFactorY: float64(gridSize-1) / (maxY - minY),
	}

	// Step 2: Map each node to the Hilbert curve
	for name, node := range nodes {
		if len(node.Coord.Vec) < 2 {
			continue
		}

		x := node.Coord.Vec[0]
		y := node.Coord.Vec[1]

		// Convert coordinates to grid positions (integers)
		nx := int((x - minX) * mapper.scaleFactorX)
		ny := int((y - minY) * mapper.scaleFactorY)

		// Clamp to grid boundaries (safety check)
		nx = clampInt(nx, 0, gridSize-1)
		ny = clampInt(ny, 0, gridSize-1)

		// Get the 1D Hilbert index for this grid cell
		idx, err := curve.MapInverse(nx, ny)
		if err != nil {
			log.Printf("Failed to map node %s: %v", name, err)
			continue
		}

		node.HilbertIdx = idx
		fmt.Printf("[MAPPING] %s | Coord: (%g, %g) | Grid: (%d, %d) | Index: %d\n",
			name, x, y, nx, ny, idx)
	}

	// Step 3: Sort nodes by Hilbert index for fast range queries
	mapper.Sorted = make([]*NodeInfo, 0, len(nodes))
	for _, node := range nodes {
		mapper.Sorted = append(mapper.Sorted, node)
	}
	sort.Slice(mapper.Sorted, func(i, j int) bool {
		return mapper.Sorted[i].HilbertIdx < mapper.Sorted[j].HilbertIdx
	})

	return mapper
}

// Finds all nodes within a given RTT (in coordinate-space units) of the target node.
func queryNodesInRTT(target *NodeInfo, rtt float64, mapper *HilbertMapper) []*NodeInfo {
	if len(target.Coord.Vec) < 2 {
		return nil
	}

	tx := target.Coord.Vec[0]
	ty := target.Coord.Vec[1]

	// Step 1: Calculate a bounding box around the target node
	xMin := clamp(tx-rtt, mapper.MinX, mapper.MaxX)
	xMax := clamp(tx+rtt, mapper.MinX, mapper.MaxX)
	yMin := clamp(ty-rtt, mapper.MinY, mapper.MaxY)
	yMax := clamp(ty+rtt, mapper.MinY, mapper.MaxY)

	// Step 2: Convert the box to grid coordinates
	nxMin := int((xMin - mapper.MinX) * mapper.scaleFactorX)
	nxMax := int((xMax - mapper.MinX) * mapper.scaleFactorX)
	nyMin := int((yMin - mapper.MinY) * mapper.scaleFactorY)
	nyMax := int((yMax - mapper.MinY) * mapper.scaleFactorY)

	// Clamp grid coordinates to valid range
	nxMin = clampInt(nxMin, 0, mapper.GridSize-1)
	nxMax = clampInt(nxMax, 0, mapper.GridSize-1)
	nyMin = clampInt(nyMin, 0, mapper.GridSize-1)
	nyMax = clampInt(nyMax, 0, mapper.GridSize-1)

	fmt.Printf("\n[QUERY] RTT: %.4f coord units\n", rtt)
	fmt.Printf("Bounding Box: X(%.4f-%.4f) Y(%.4f-%.4f)\n", xMin, xMax, yMin, yMax)
	fmt.Printf("Grid Search: X(%d-%d) Y(%d-%d)\n", nxMin, nxMax, nyMin, nyMax)

	// Step 3: Find all Hilbert indices in the search box
	indexSet := make(map[int]struct{})
	for x := nxMin; x <= nxMax; x++ {
		for y := nyMin; y <= nyMax; y++ {
			idx, err := mapper.curve.MapInverse(x, y)
			if err == nil {
				indexSet[idx] = struct{}{} // Store unique indices
			}
		}
	}

	// Step 4: Merge consecutive indices into ranges (optimization)
	indices := make([]int, 0, len(indexSet))
	for idx := range indexSet {
		indices = append(indices, idx)
	}
	sort.Ints(indices)
	ranges := mergeRanges(indices)

	// Step 5: Binary search to find nodes in the Hilbert index ranges
	var candidates []*NodeInfo
	for _, r := range ranges {
		start, end := r[0], r[1]
		left := sort.Search(len(mapper.Sorted), func(i int) bool {
			return mapper.Sorted[i].HilbertIdx >= start
		})
		right := sort.Search(len(mapper.Sorted), func(i int) bool {
			return mapper.Sorted[i].HilbertIdx > end
		})
		candidates = append(candidates, mapper.Sorted[left:right]...)
	}

	// Step 6: Filter by actual distance (in case the box was too generous)
	var results []*NodeInfo
	tx, ty = target.Coord.Vec[0], target.Coord.Vec[1]
	for _, node := range candidates {
		if node.Name == target.Name {
			continue // Skip the target node
		}
		dx := node.Coord.Vec[0] - tx
		dy := node.Coord.Vec[1] - ty
		distance := math.Sqrt(dx*dx + dy*dy)
		if distance <= rtt {
			results = append(results, node)
		}
	}

	return results
}

// --- Helper Functions ---

// Gets the current node's name (assumes a specific naming convention).
func getCurrentNodeName() string {
	hostname, err := os.Hostname()
	if err != nil {
		log.Fatal("Hostname detection failed:", err)
	}
	return fmt.Sprintf("clab-nebula-%s", hostname)
}

// Clamps a float value between lo and hi.
func clamp(v, lo, hi float64) float64 {
	return math.Max(lo, math.Min(hi, v))
}

// Clamps an integer value between lo and hi.
func clampInt(v, lo, hi int) int {
	if v < lo {
		return lo
	} else if v > hi {
		return hi
	}
	return v
}

// Merges consecutive integers into ranges (e.g., [1,2,3,5] → [[1,3], [5,5]]).
func mergeRanges(indices []int) [][]int {
	var ranges [][]int
	if len(indices) == 0 {
		return ranges
	}

	start := indices[0]
	end := indices[0]
	for _, idx := range indices[1:] {
		if idx == end+1 {
			end = idx // Extend the current range
		} else {
			ranges = append(ranges, []int{start, end})
			start = idx
			end = idx
		}
	}
	ranges = append(ranges, []int{start, end})
	return ranges
}

// Prints search results in a readable format.
func printResults(results []*NodeInfo, currentNode string, rttMs float64) {
	if len(results) == 0 {
		fmt.Printf("\nNo nodes found within %.2f ms\n", rttMs)
		return
	}

	fmt.Printf("\n=== Nodes within %.2f ms of %s ===\n", rttMs, currentNode)
	for i, node := range results {
		dx := node.Coord.Vec[0] - results[0].Coord.Vec[0]
		dy := node.Coord.Vec[1] - results[0].Coord.Vec[1]
		distance := math.Sqrt(dx*dx + dy*dy)
		fmt.Printf("%3d. %-20s Hilbert Index: %6d Distance: %.4f\n",
			i+1, node.Name, node.HilbertIdx, distance)
	}
}
