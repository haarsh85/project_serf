package main

import (
	"fmt"
	"log"
	"os"
	"time"

	"github.com/hashicorp/serf/client"
)

func main() {
	// Set up logging to a file
	logFile, err := os.OpenFile("coordinates.log", os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		log.Fatalf("Failed to open log file: %v", err)
	}
	defer logFile.Close()
	logger := log.New(logFile, "", log.LstdFlags)

	// Serf RPC client configuration
	clientConfig := &client.Config{
		Addr: "127.0.0.1:7373", // Local Serf agent RPC address
	}

	// Create Serf RPC client
	serfClient, err := client.ClientFromConfig(clientConfig)
	if err != nil {
		log.Fatalf("Failed to create Serf client: %v", err)
	}
	defer serfClient.Close()

	for {
		// Retrieve cluster members
		members, err := serfClient.Members()
		if err != nil {
			log.Fatalf("Failed to get members: %v", err)
		}

		for _, member := range members {
			// Get coordinate for current member
			coord, err := serfClient.GetCoordinate(member.Name)
			if err != nil {
				fmt.Printf("Error getting coordinate for %s: %v\n", member.Name, err)
				continue
			}

			// Format and log coordinate details
			logEntry := fmt.Sprintf(
				"Time: %s - Node: %s | Vec: %v | Error: %.5f | Adjustment: %.5f | Height: %.5f",
				time.Now().Format(time.RFC3339),
				member.Name,
				coord.Vec,
				coord.Error,
				coord.Adjustment,
				coord.Height,
			)

			// Print to console and write to log file
			fmt.Println(logEntry)
			logger.Println(logEntry)
		}

		// Wait before next poll
		time.Sleep(10 * time.Second)
	}
}
