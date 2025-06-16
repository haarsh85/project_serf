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
	"strings"
)

// Coordinate holds the vector and associated attributes.
type Coordinate struct {
	Node       string
	Vec        []float64
	Error      float64
	Adjustment float64
	Height     float64
}

// calculateRTT calculates the RTT between two Vivaldi coordinates
func calculateRTT(a, b *Coordinate) float64 {
	// Calculate the Euclidean distance plus the heights.
	sumsq := 0.0
	for i := 0; i < len(a.Vec); i++ {
		diff := a.Vec[i] - b.Vec[i]
		sumsq += diff * diff
	}
	rtt := math.Sqrt(sumsq) + a.Height + b.Height

	// Apply the adjustment components, guarding against negatives.
	adjusted := rtt + a.Adjustment + b.Adjustment
	if adjusted > 0.0 {
		rtt = adjusted
	}

	return rtt * 1000 // Convert to milliseconds
}

// parseLogFile parses the log file and returns the coordinates.
func parseLogFile(filePath string) ([]Coordinate, error) {
	var coordinates []Coordinate

	file, err := os.Open(filePath)
	if err != nil {
		return nil, err
	}
	defer file.Close()

	// Regular expression to extract node info from the log line
	re := regexp.MustCompile(`Node: (\S+) \| Vec: \[([^\]]+)\] \| Error: ([^|]+) \| Adjustment: ([^|]+) \| Height: ([^\n]+)`)

	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := scanner.Text()

		matches := re.FindStringSubmatch(line)
		if len(matches) != 6 {
			// Skip lines that don't match the expected format
			continue
		}

		// Extract node info from the log line
		node := matches[1]
		vecStr := matches[2]
		errorStr := matches[3]
		adjustmentStr := matches[4]
		heightStr := matches[5]

		// Convert the vector to a float64 array
		vecParts := strings.Split(vecStr, " ")
		var vec []float64
		for _, v := range vecParts {
			if v != "" {
				val, err := strconv.ParseFloat(v, 64)
				if err != nil {
					log.Fatalf("Error parsing vector value: %v\n", err)
				}
				vec = append(vec, val)
			}
		}

		// Parse the other fields
		errorVal, err := strconv.ParseFloat(errorStr, 64)
		if err != nil {
			log.Fatalf("Error parsing error value: %v\n", err)
		}
		adjustmentVal, err := strconv.ParseFloat(adjustmentStr, 64)
		if err != nil {
			log.Fatalf("Error parsing adjustment value: %v\n", err)
		}
		heightVal, err := strconv.ParseFloat(heightStr, 64)
		if err != nil {
			log.Fatalf("Error parsing height value: %v\n", err)
		}

		// Add the parsed coordinate to the list
		coordinates = append(coordinates, Coordinate{
			Node:       node,
			Vec:        vec,
			Error:      errorVal,
			Adjustment: adjustmentVal,
			Height:     heightVal,
		})
	}

	if err := scanner.Err(); err != nil {
		return nil, err
	}

	return coordinates, nil
}

// nodeNameToInt extracts the numeric part of the node name and converts it to an integer for sorting
func nodeNameToInt(nodeName string) (int, error) {
	// Find all numbers in the node name
	re := regexp.MustCompile(`\d+`)
	matches := re.FindAllString(nodeName, -1)
	if len(matches) == 0 {
		return 0, fmt.Errorf("no numbers found in node name: %s", nodeName)
	}

	// Take the last number (in case there are multiple)
	nodeNumber, err := strconv.Atoi(matches[len(matches)-1])
	if err != nil {
		return 0, fmt.Errorf("error converting node number to integer: %v", err)
	}

	return nodeNumber, nil
}

// main function to read the file and calculate RTT for each node pair
func main() {
	// Path to the coordinates log file
	filePath := "coordinates.log"       // Adjust this if needed
	outputFilePath := "rtt_results.log" // Output file path

	// Parse the log file to get the coordinates
	coordinates, err := parseLogFile(filePath)
	if err != nil {
		log.Fatalf("Error reading log file: %v\n", err)
	}

	// Sort coordinates by node number (numerical order)
	sort.Slice(coordinates, func(i, j int) bool {
		nodeNumI, _ := nodeNameToInt(coordinates[i].Node)
		nodeNumJ, _ := nodeNameToInt(coordinates[j].Node)
		return nodeNumI < nodeNumJ
	})

	// Create or open the output file to write the results
	outputFile, err := os.Create(outputFilePath)
	if err != nil {
		log.Fatalf("Error creating output file: %v\n", err)
	}
	defer outputFile.Close()

	// Create a writer to write to the file
	writer := bufio.NewWriter(outputFile)

	// Calculate RTT values between each node pair in sorted order
	for i := 0; i < len(coordinates); i++ {
		// Calculate RTTs with all higher-numbered nodes
		for j := i + 1; j < len(coordinates); j++ {
			rtt := calculateRTT(&coordinates[i], &coordinates[j])

			// Write the RTT result to the output file
			_, err := fmt.Fprintf(writer, "Estimated RTT from %s to %s: %.2f ms\n",
				coordinates[i].Node, coordinates[j].Node, rtt)
			if err != nil {
				log.Fatalf("Error writing to output file: %v\n", err)
			}
		}

		// Add an empty line between different "from" nodes for better readability
		if i < len(coordinates)-1 {
			fmt.Fprintln(writer)
		}
	}

	// Flush the buffered writer to ensure all data is written to the file
	writer.Flush()

	fmt.Println("RTT results have been written to", outputFilePath)
}
