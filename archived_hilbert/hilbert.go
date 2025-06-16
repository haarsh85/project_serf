package main

import (
	"fmt"
	"log"
	"math"
	"os"

	"github.com/google/hilbert"
	"github.com/hashicorp/serf/client"
)

type NodeData struct {
	Name         string
	OriginalX    float64
	OriginalY    float64
	NormalizedX  int
	NormalizedY  int
	HilbertIndex int
}

func main() {
	// 1. Get current node name from hostname
	selfName, err := getNodeName()
	if err != nil {
		log.Fatalf("Error getting node name: %v", err)
	}

	// 2. Initialize Serf client
	serfClient, err := client.ClientFromConfig(&client.Config{Addr: "127.0.0.1:7373"})
	if err != nil {
		log.Fatalf("Serf connection failed: %v", err)
	}
	defer serfClient.Close()

	// 3. Collect all node coordinates
	members, err := serfClient.Members()
	if err != nil {
		log.Fatalf("Failed to get members: %v", err)
	}

	// 4. First pass: collect all coordinates to determine min/max
	var allCoords []struct{ x, y float64 }
	for _, member := range members {
		coord, err := serfClient.GetCoordinate(member.Name)
		if err != nil || len(coord.Vec) != 2 {
			continue
		}
		allCoords = append(allCoords, struct{ x, y float64 }{coord.Vec[0], coord.Vec[1]})
	}

	// 5. Calculate normalization parameters
	minX, maxX, minY, maxY := calculateBounds(allCoords)

	// 6. Initialize Hilbert space (start with order 8 = 2^3)
	hilbertOrder := 16 // You can increase this to 16, 32, 64, etc.
	h, err := hilbert.NewHilbert(hilbertOrder)
	if err != nil {
		log.Fatalf("Hilbert init failed: %v", err)
	}

	// 7. Second pass: process all nodes
	var nodes []NodeData
	for _, member := range members {
		coord, err := serfClient.GetCoordinate(member.Name)
		if err != nil || len(coord.Vec) != 2 {
			continue
		}

		// Normalize coordinates to [0, N-1] grid
		normX := normalize(coord.Vec[0], minX, maxX, h.N)
		normY := normalize(coord.Vec[1], minY, maxY, h.N)

		// Get Hilbert index
		t, err := h.MapInverse(normX, normY)
		if err != nil {
			log.Printf("Invalid coordinates for %s: %v", member.Name, err)
			continue
		}

		nodes = append(nodes, NodeData{
			Name:         member.Name,
			OriginalX:    coord.Vec[0],
			OriginalY:    coord.Vec[1],
			NormalizedX:  normX,
			NormalizedY:  normY,
			HilbertIndex: t,
		})
	}

	// 8. Print results
	printResults(nodes, selfName, hilbertOrder, minX, maxX, minY, maxY)
}

// Helper functions
func getNodeName() (string, error) {
	hostname, err := os.Hostname()
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("clab-nebula-%s", hostname), nil
}

func calculateBounds(coords []struct{ x, y float64 }) (minX, maxX, minY, maxY float64) {
	if len(coords) == 0 {
		return 0, 1, 0, 1 // Default bounds if no coordinates
	}

	minX, maxX = coords[0].x, coords[0].x
	minY, maxY = coords[0].y, coords[0].y

	for _, c := range coords {
		minX = math.Min(minX, c.x)
		maxX = math.Max(maxX, c.x)
		minY = math.Min(minY, c.y)
		maxY = math.Max(maxY, c.y)
	}

	// Add 10% padding to prevent edge cases
	paddingX := (maxX - minX) * 0.1
	paddingY := (maxY - minY) * 0.1
	return minX - paddingX, maxX + paddingX, minY - paddingY, maxY + paddingY
}

func normalize(val, min, max float64, n int) int {
	if max == min {
		return 0 // Handle identical coordinates
	}
	scaled := (val - min) / (max - min) * float64(n-1)
	return int(math.Round(math.Max(0, math.Min(float64(n-1), scaled))))
}

func printResults(nodes []NodeData, selfName string, order int, minX, maxX, minY, maxY float64) {
	fmt.Println("\nHilbert Space Configuration:")
	fmt.Printf("\n- Order: %d (N=%d)", order, order)
	fmt.Printf("\n- Grid Size: %dx%d", order, order)
	fmt.Println("\n- X Range:", minX, maxX)
	fmt.Println("- Y Range:", minY, maxY)

	fmt.Println("\nCurrent Node:\n", selfName)
	fmt.Println("\nAll Nodes:")
	fmt.Println("Name\t\tOriginal X\tOriginal Y\tNorm X\tNorm Y\tHilbert Index")
	fmt.Println("-------------------------------------------------------------------------")

	for _, node := range nodes {
		fmt.Println(node.Name, "\t", node.OriginalX, "\t", node.OriginalY, "\t", node.NormalizedX, "\t", node.NormalizedY, "\t", node.HilbertIndex)
	}
}
