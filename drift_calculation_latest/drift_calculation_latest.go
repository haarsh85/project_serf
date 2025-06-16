package main

import (
	"fmt"
	"log"
	"math"
	"os"
	"time"

	"github.com/hashicorp/serf/client"
	"github.com/hashicorp/serf/coordinate"
)

func main() {
	// Log file setup
	logFile, err := os.OpenFile("drift.log", os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		log.Fatalf("Failed to open log file: %v", err)
	}
	defer logFile.Close()

	// Custom logger without timestamp prefix (we'll add it ourselves)
	logger := log.New(logFile, "", 0)

	// Serf client setup
	serfClient, err := client.ClientFromConfig(&client.Config{Addr: "127.0.0.1:7373"})
	if err != nil {
		log.Fatalf("Failed to create Serf client: %v", err)
	}
	defer serfClient.Close()

	// Origin coordinate setup
	config := coordinate.DefaultConfig()
	origin := coordinate.NewCoordinate(config)
	for i := range origin.Vec {
		origin.Vec[i] = 0.0
	}
	origin.Adjustment = 0.0

	// Load Berlin timezone
	loc, err := time.LoadLocation("Europe/Berlin")
	if err != nil {
		log.Fatalf("Failed to load timezone: %v", err)
	}

	// Main loop
	ticker := time.NewTicker(1 * time.Minute)
	defer ticker.Stop()

	for range ticker.C {
		members, err := serfClient.Members()
		if err != nil {
			log.Printf("Error fetching members: %v", err)
			continue
		}

		for _, member := range members {
			coord, err := serfClient.GetCoordinate(member.Name)
			if err != nil || coord == nil {
				continue
			}

			// Calculate metrics
			timestamp := time.Now().In(loc).Format(time.RFC3339)
			vecDist := vecDistanceFromOrigin(coord)
			totalDrift := coord.DistanceTo(origin).Seconds() * 1000 // ms

			// Format log line
			logLine := fmt.Sprintf(
				"NODE_DRIFT,time=%s,node=%s,vec_distance_ms=%.2f,total_drift_ms=%.2f,height=%.6f,adjustment=%.6f",
				timestamp,
				member.Name,
				vecDist*1000,
				totalDrift,
				coord.Height,
				coord.Adjustment,
			)

			// Write to file and console
			logger.Println(logLine)     // Log file
			fmt.Println(logLine)        // Console
		}
	}
}

func vecDistanceFromOrigin(coord *coordinate.Coordinate) float64 {
	sumSq := 0.0
	for _, v := range coord.Vec {
		sumSq += v * v
	}
	return math.Sqrt(sumSq)
}