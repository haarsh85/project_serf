package main

import (
	"flag"
	"fmt"
	"log"
	"math"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/hashicorp/serf/client"
	"github.com/hashicorp/serf/coordinate"
)

const (
	clusterPrefix = "clab-nebula-serf"
	serfRPCPort   = "7373"
)

func main() {
	// Command-line flags
	targetFlag := flag.String("target", "", "Node number to monitor (e.g., 1)")
	observersFlag := flag.String("observers", "", "Comma-separated observer node numbers (e.g., 10,20,50)")
	flag.Parse()

	// Validate input
	if *targetFlag == "" {
		log.Fatal("Error: --target flag is required")
	}

	// Generate full node names
	targetNode := formatNodeName(*targetFlag)
	observerNodes := parseObserverNodes(*observersFlag)

	// Set up logging
	logFile, err := os.OpenFile("coordinates.log", os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		log.Fatal(err)
	}
	defer logFile.Close()
	logger := log.New(logFile, "", log.LstdFlags)

	// Main monitoring loop
	for {
		clearScreen()
		log.Printf("=== Monitoring coordinates for Node %s ===", *targetFlag)

		// Get coordinates from all observers
		results := queryObservers(targetNode, observerNodes)

		// Display results
		printResults(targetNode, results, *targetFlag, logger)

		time.Sleep(10 * time.Second)
	}
}

// formatNodeName converts number or name to full node name
func formatNodeName(input string) string {
	// Try to parse as number first
	if num, err := strconv.Atoi(input); err == nil {
		return fmt.Sprintf("%s%d", clusterPrefix, num)
	}

	// Handle if input already contains "serf"
	if strings.Contains(input, "serf") {
		return clusterPrefix + strings.TrimPrefix(input, "serf")
	}

	// Return full name if already formatted
	if strings.HasPrefix(input, clusterPrefix) {
		return input
	}

	// Fallback to numeric conversion
	return fmt.Sprintf("%s%s", clusterPrefix, input)
}

// parseObserverNodes converts numbers to full node names
func parseObserverNodes(input string) []string {
	var nodes []string
	if input == "" {
		return nodes
	}

	parts := strings.Split(input, ",")
	for _, p := range parts {
		p = strings.TrimSpace(p)
		if p != "" {
			nodes = append(nodes, formatNodeName(p))
		}
	}
	return nodes
}

func queryObservers(target string, observers []string) map[string]*coordinate.Coordinate {
	results := make(map[string]*coordinate.Coordinate)

	for _, observer := range observers {
		coord, err := getCoordinateFromNode(observer, target)
		if err != nil {
			log.Printf("Node %s: Connection failed (%v)", getNodeNumber(observer), err)
			continue
		}
		results[observer] = coord
	}
	return results
}

func getCoordinateFromNode(observer, target string) (*coordinate.Coordinate, error) {
	client, err := client.ClientFromConfig(&client.Config{
		Addr:    fmt.Sprintf("%s:%s", observer, serfRPCPort),
		Timeout: 5 * time.Second,
	})
	if err != nil {
		return nil, err
	}
	defer client.Close()

	return client.GetCoordinate(target)
}

// func printResults(target string, results map[string]*coordinate.Coordinate, targetNumber string, logger *log.Logger) {
// 	ts := time.Now().Format("2006-01-02 15:04:05")

// 	// Target's own coordinates (self-view)
// 	selfCoord, selfErr := getCoordinateFromNode(target, target)
// 	if selfErr == nil {
// 		msg := fmt.Sprintf("[%s] Node %s SELF VIEW", ts, targetNumber)
// 		printCoordinate(msg, selfCoord)
// 		logger.Println(formatLogEntry(target, target, selfCoord))
// 	}

// 	// Observer coordinates
// 	for observer, coord := range results {
// 		obsNumber := getNodeNumber(observer)
// 		msg := fmt.Sprintf("[%s] Node %s's view", ts, obsNumber)
// 		printCoordinate(msg, coord)
// 		logger.Println(formatLogEntry(observer, target, coord))
// 	}

// 	fmt.Println("\n" + strings.Repeat("=", 60))
// }

func printResults(target string, results map[string]*coordinate.Coordinate, targetNumber string, logger *log.Logger) {
	ts := time.Now().Format("2006-01-02 15:04:05")

	// Get Node A's self-reported coordinates
	selfCoord, selfErr := getCoordinateFromNode(target, target)
	if selfErr != nil {
		log.Printf("Failed to get self-coordinate for %s: %v", target, selfErr)
		return
	}

	// Print Node A's own view
	msg := fmt.Sprintf("[%s] Node %s SELF VIEW", ts, targetNumber)
	printCoordinate(msg, selfCoord)
	logger.Println(formatLogEntry(target, target, selfCoord))

	// Process each observer
	for observer, coord := range results {
		if coord == nil {
			continue // Skip failed connections
		}

		obsNumber := getNodeNumber(observer)

		// 1. Show observer's view of target's coordinates (original functionality)
		viewMsg := fmt.Sprintf("[%s] Node %s's view of Node %s", ts, obsNumber, targetNumber)
		printCoordinate(viewMsg, coord)
		logger.Println(formatLogEntry(observer, target, coord))

		// 2. Show differences (new functionality)
		// Calculate adjusted difference in ms
		adjustedDiff := selfCoord.DistanceTo(coord)
		adjustedMs := float64(adjustedDiff.Nanoseconds()) / 1e6

		// Calculate raw difference in ms
		rawSeconds := calculateRawDistance(selfCoord, coord)
		rawMs := rawSeconds * 1000

		fmt.Printf("  ┣ Comparison to Target:")
		// fmt.Printf("\n  ┃   ┣ Adjusted Difference: %.3fms (network estimate)", adjustedMs)
		fmt.Printf("\n  ┃   ┗ Raw Difference:     %.3fms (pure coordinates)\n", rawMs)

		// Log differences
		logger.Printf("%s | Observer:%s | AdjustedDiff:%.3fms | RawDiff:%.3fms",
			time.Now().Format(time.RFC3339),
			obsNumber,
			adjustedMs,
			rawMs,
		)
	}

	fmt.Println("\n" + strings.Repeat("=", 60))
}

// calculateRawDistance replicates the unexported rawDistanceTo logic
func calculateRawDistance(a, b *coordinate.Coordinate) float64 {
	// Check dimensionality match
	if len(a.Vec) != len(b.Vec) {
		return math.NaN() // Indicate error
	}

	// Calculate Euclidean distance between vectors
	dist := 0.0
	for i := range a.Vec {
		diff := a.Vec[i] - b.Vec[i]
		dist += diff * diff
	}
	dist = math.Sqrt(dist)

	// Add heights from both coordinates
	return dist + a.Height + b.Height
}

func getNodeNumber(fullName string) string {
	return strings.TrimPrefix(fullName, clusterPrefix)
}

func printCoordinate(header string, c *coordinate.Coordinate) {
	fmt.Printf("\n%s\n", header)
	fmt.Printf("  ┣ Vector:    %v\n", c.Vec)
	fmt.Printf("  ┣ Error:     %.5f\n", c.Error)
	fmt.Printf("  ┣ Adjustment:%.5f\n", c.Adjustment)
	fmt.Printf("  ┗ Height:    %.5f\n", c.Height)
}

func formatLogEntry(observer, target string, c *coordinate.Coordinate) string {
	return fmt.Sprintf("%s | Observer:%s | Target:%s | Vec:%v | Err:%.5f | Adj:%.5f | Ht:%.5f",
		time.Now().Format(time.RFC3339),
		getNodeNumber(observer),
		getNodeNumber(target),
		c.Vec,
		c.Error,
		c.Adjustment,
		c.Height,
	)
}

func clearScreen() {
	fmt.Print("\033[H\033[2J") // ANSI escape codes for clear screen
}
