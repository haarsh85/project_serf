package main

import (
	"fmt"
	"log"
	"math"
	"os"
	"time"

	"github.com/google/hilbert" // For Hilbert transformation
	"github.com/hashicorp/serf/client"
)

func main() {
	// Set up logging to a file
	logFile, err := os.OpenFile("node_coordinates.log", os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		log.Fatalf("Failed to open log file: %v", err)
	}
	defer logFile.Close()
	logger := log.New(logFile, "", log.LstdFlags)

	// Set up the Serf RPC client configuration
	clientConfig := &client.Config{
		Addr: "127.0.0.1:7373", // Use localhost for RPC address
	}

	// Create a Serf RPC client
	serfClient, err := client.ClientFromConfig(clientConfig)
	if err != nil {
		log.Fatalf("Failed to create Serf client: %v", err)
	}
	defer serfClient.Close()

	// Initialize the Hilbert curve with the desired order
	order := 2                // Adjust order based on your grid size
	maxGridSize := 1 << order // Grid size is 2^order (e.g., 16x16 for order 4)
	hilbertSpace, err := hilbert.NewHilbert(maxGridSize)
	if err != nil {
		log.Fatalf("Failed to initialize Hilbert space: %v", err)
	}

	for {
		// Retrieve members from the Serf client
		clientMembers, err := serfClient.Members()
		if err != nil {
			log.Fatalf("Failed to retrieve members from client: %v", err)
		}

		// Initialize min/max values for normalization
		minX, maxX := math.MaxFloat64, -math.MaxFloat64
		minY, maxY := math.MaxFloat64, -math.MaxFloat64

		// First Pass: Calculate min and max for x and y coordinates
		for _, member := range clientMembers {
			coord, err := serfClient.GetCoordinate(member.Name)
			if err != nil {
				fmt.Printf("Failed to get coordinate for node %s: %v\n", member.Name, err)
				continue
			}
			// Update min and max values
			minX = math.Min(minX, coord.Vec[0])
			maxX = math.Max(maxX, coord.Vec[0])
			minY = math.Min(minY, coord.Vec[1])
			maxY = math.Max(maxY, coord.Vec[1])
		}

		// Second Pass: Normalize and calculate Hilbert values
		for _, member := range clientMembers {
			coord, err := serfClient.GetCoordinate(member.Name)
			if err != nil {
				fmt.Printf("Failed to get coordinate for node %s: %v\n", member.Name, err)
				continue
			}

			// Print the node details first
			fmt.Printf("Node: %s, Address: %s:%d, Status: %s, Tags: %v\n",
				member.Name, member.Addr, member.Port, member.Status, member.Tags)

			// Log Vivaldi coordinate
			logger.Printf("Vivaldi Coordinate for %s: %+v\n", member.Name, coord)
			fmt.Printf("Vivaldi Coordinate for %s: %+v\n", member.Name, coord)

			// Normalize Vivaldi coordinates to [0, N-1] range
			x := int((coord.Vec[0] - minX) * float64(maxGridSize-1) / (maxX - minX))
			y := int((coord.Vec[1] - minY) * float64(maxGridSize-1) / (maxY - minY))

			// Ensure x and y are within bounds (0, maxGridSize-1)
			if x < 0 {
				x = 0
			} else if x >= maxGridSize {
				x = maxGridSize - 1
			}
			if y < 0 {
				y = 0
			} else if y >= maxGridSize {
				y = maxGridSize - 1
			}

			// Perform the Hilbert transformation (2D to 1D)
			t, err := hilbertSpace.MapInverse(x, y)
			if err != nil {
				fmt.Printf("Failed to perform Hilbert transformation for node %s: %v\n", member.Name, err)
			} else {
				// Log and print the Hilbert transformation result (1D)
				logger.Printf("Hilbert Transformation (2D to 1D) for %s: 1D value: %d\n", member.Name, t)
				fmt.Printf("Hilbert Transformation (2D to 1D) for %s: 1D value: %d\n", member.Name, t)
			}
		}

		// Wait for a specified duration before checking again
		time.Sleep(5 * time.Second) // Adjust the interval as needed
	}
}
