package main

import (
	"bufio"
	"fmt"
	"log"
	"math"
	"os"
	"regexp"
	"sort"
	"strconv"

	"github.com/google/hilbert"
)

// NodeCoord holds node coordinates and Hilbert index
type NodeCoord struct {
	Name   string
	X, Y   float64
	NX, NY int
	Index  int
}

// RTTRecord holds RTT measurement between two nodes
type RTTRecord struct {
	FromNode string
	ToNode   string
	RTT      float64
}

func main() {
	// Step 1: Process coordinates and create Hilbert mapping
	nodes := processCoordinates("coordinates.log")

	// Step 2: Parse RTT data from different sources
	pingRTTs := parseRTTFile("ping_sorted_rtt_new.log", "ping")
	serfRTTs := parseRTTFile("serf_rtt_results_from_coordinateslog.log", "serf")

	// Step 3: Query node setup
	queryNode := "clab-nebula-serf1"
	queryIndex := -1
	for _, n := range nodes {
		if n.Name == queryNode {
			queryIndex = n.Index
			break
		}
	}
	if queryIndex == -1 {
		log.Fatalf("Query node %s not found", queryNode)
	}

	// Step 4: Get Hilbert-based neighbors
	rangeThreshold := 1117
	hilbertNeighbors := getHilbertNeighbors(nodes, queryIndex, rangeThreshold)

	// Step 5: Get nearest neighbors based on RTT measurements
	pingNeighbors := getNearestNeighbors(pingRTTs, queryNode, 10)
	serfNeighbors := getNearestNeighbors(serfRTTs, queryNode, 10)

	// Step 6: Print results
	printResults(queryNode, nodes, hilbertNeighbors, pingNeighbors, serfNeighbors)
}

func processCoordinates(filename string) []NodeCoord {
	file, err := os.Open(filename)
	if err != nil {
		log.Fatalf("Failed to open %s: %v", filename, err)
	}
	defer file.Close()

	var nodes []NodeCoord
	re := regexp.MustCompile(`Node: (\S+) \| Vec: \[([\d\.\-\+eE]+) ([\d\.\-\+eE]+)\]`)

	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := scanner.Text()
		matches := re.FindStringSubmatch(line)
		if matches != nil {
			name := matches[1]
			x, _ := strconv.ParseFloat(matches[2], 64)
			y, _ := strconv.ParseFloat(matches[3], 64)
			nodes = append(nodes, NodeCoord{Name: name, X: x, Y: y})
		}
	}

	if err := scanner.Err(); err != nil {
		log.Fatalf("Error reading file: %v", err)
	}

	// Normalize coordinates
	minX, maxX := math.MaxFloat64, -math.MaxFloat64
	minY, maxY := math.MaxFloat64, -math.MaxFloat64
	for _, n := range nodes {
		if n.X < minX {
			minX = n.X
		}
		if n.X > maxX {
			maxX = n.X
		}
		if n.Y < minY {
			minY = n.Y
		}
		if n.Y > maxY {
			maxY = n.Y
		}
	}

	// Create Hilbert curve mapping
	gridSize := 512
	h, err := hilbert.NewHilbert(gridSize)
	if err != nil {
		log.Fatalf("Failed to create Hilbert curve: %v", err)
	}

	for i := range nodes {
		n := &nodes[i]
		n.NX = int(((n.X - minX) / (maxX - minX)) * float64(gridSize-1))
		n.NY = int(((n.Y - minY) / (maxY - minY)) * float64(gridSize-1))

		t, err := h.MapInverse(n.NX, n.NY)
		if err != nil {
			log.Fatalf("Failed to map node %s: %v", n.Name, err)
		}
		n.Index = t
	}

	// Sort nodes by Hilbert index
	sort.Slice(nodes, func(i, j int) bool {
		return nodes[i].Index < nodes[j].Index
	})

	return nodes
}

func parseRTTFile(filename, rttType string) []RTTRecord {
	file, err := os.Open(filename)
	if err != nil {
		log.Fatalf("Failed to open %s: %v", filename, err)
	}
	defer file.Close()

	var records []RTTRecord
	var re *regexp.Regexp

	if rttType == "ping" {
		re = regexp.MustCompile(`\[net_\d+\] (\S+) \(\d+\.\d+\.\d+\.\d+\) → \[net_\d+\] (\S+) \(\d+\.\d+\.\d+\.\d+\): ([\d\.]+)ms`)
	} else {
		re = regexp.MustCompile(`Estimated RTT from (\S+) to (\S+): ([\d\.]+) ms`)
	}

	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := scanner.Text()
		matches := re.FindStringSubmatch(line)
		if matches != nil {
			from := matches[1]
			to := matches[2]
			rtt, _ := strconv.ParseFloat(matches[3], 64)
			records = append(records, RTTRecord{FromNode: from, ToNode: to, RTT: rtt})
		}
	}

	if err := scanner.Err(); err != nil {
		log.Fatalf("Error reading file: %v", err)
	}

	return records
}

func getHilbertNeighbors(nodes []NodeCoord, queryIndex, rangeThreshold int) []string {
	minIndex := queryIndex - rangeThreshold
	maxIndex := queryIndex + rangeThreshold

	var neighbors []string
	for _, n := range nodes {
		if n.Index >= minIndex && n.Index <= maxIndex {
			neighbors = append(neighbors, n.Name)
		}
	}
	return neighbors
}

func getNearestNeighbors(records []RTTRecord, queryNode string, count int) []RTTRecord {
	var relevant []RTTRecord
	for _, r := range records {
		if r.FromNode == queryNode {
			relevant = append(relevant, r)
		}
	}

	sort.Slice(relevant, func(i, j int) bool {
		return relevant[i].RTT < relevant[j].RTT
	})

	if len(relevant) > count {
		return relevant[:count]
	}
	return relevant
}

func printResults(queryNode string, nodes []NodeCoord, hilbertNeighbors []string, pingNeighbors, serfNeighbors []RTTRecord) {
	// Find query node info
	var queryNodeInfo NodeCoord
	for _, n := range nodes {
		if n.Name == queryNode {
			queryNodeInfo = n
			break
		}
	}

	fmt.Printf("\n=== Node Information ===\n")
	fmt.Printf("Query Node: %s\n", queryNode)
	fmt.Printf("Coordinates: (%.5f, %.5f)\n", queryNodeInfo.X, queryNodeInfo.Y)
	fmt.Printf("Normalized: (%d, %d)\n", queryNodeInfo.NX, queryNodeInfo.NY)
	fmt.Printf("Hilbert Index: %d\n", queryNodeInfo.Index)

	fmt.Printf("\n=== Hilbert Curve Neighbors ===\n")
	for _, n := range hilbertNeighbors {
		fmt.Println(n)
	}

	fmt.Printf("\n=== Nearest Neighbors by Ping RTT ===\n")
	for _, r := range pingNeighbors {
		fmt.Printf("%s: %.3f ms\n", r.ToNode, r.RTT)
	}

	fmt.Printf("\n=== Nearest Neighbors by Serf RTT ===\n")
	for _, r := range serfNeighbors {
		fmt.Printf("%s: %.3f ms\n", r.ToNode, r.RTT)
	}

	// Compare the results
	fmt.Printf("\n=== Comparison of Results ===\n")
	fmt.Println("Hilbert neighbors count:", len(hilbertNeighbors))
	fmt.Println("Ping top neighbors count:", len(pingNeighbors))
	fmt.Println("Serf top neighbors count:", len(serfNeighbors))

	// Check how many ping top neighbors are in Hilbert neighbors
	var commonWithPing int
	for _, ping := range pingNeighbors {
		for _, hilbert := range hilbertNeighbors {
			if ping.ToNode == hilbert {
				commonWithPing++
				break
			}
		}
	}
	fmt.Printf("Ping top neighbors in Hilbert neighbors: %d/%d\n", commonWithPing, len(pingNeighbors))

	// Check how many serf top neighbors are in Hilbert neighbors
	var commonWithSerf int
	for _, serf := range serfNeighbors {
		for _, hilbert := range hilbertNeighbors {
			if serf.ToNode == hilbert {
				commonWithSerf++
				break
			}
		}
	}
	fmt.Printf("Serf top neighbors in Hilbert neighbors: %d/%d\n", commonWithSerf, len(serfNeighbors))
}
