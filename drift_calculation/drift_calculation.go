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

type Centroid struct {
	Vec    []float64
	Height float64
	Adjustment float64
	Count  int
}

func main() {
	// Configure logging for centroid drift
	logFile, err := os.OpenFile("centroid_drift.log", os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		log.Fatalf("Failed to open log file: %v", err)
	}
	defer logFile.Close()
	logger := log.New(logFile, "", log.LstdFlags)

	serfClient, err := client.ClientFromConfig(&client.Config{Addr: "127.0.0.1:7373"})
	if err != nil {
		log.Fatalf("Failed to create Serf client: %v", err)
	}
	defer serfClient.Close()

	config := coordinate.DefaultConfig()
	// Create synthetic origin coordinate 
	origin := coordinate.NewCoordinate(config)
	for i := range origin.Vec {
		origin.Vec[i] = 0.0 // Explicitly zero the origin vector
	}

	origin.Height = config.HeightMin
	origin.Adjustment = 0.0

	ticker := time.NewTicker(1 * time.Minute) // Check every 1 minutes for drift
	defer ticker.Stop()

	for range ticker.C {
		members, err := serfClient.Members()
		if err != nil {
			log.Printf("Error fetching members: %v", err)
			continue
		}

		centroid := &Centroid{}

		// Compute centroid of all coordinates
		for _, member := range members {
			coord, err := serfClient.GetCoordinate(member.Name)
			if err != nil || coord == nil {
				continue
			}

			if centroid.Count == 0 {
				centroid.Vec = make([]float64, len(coord.Vec))
			}

			for i := range coord.Vec {
				centroid.Vec[i] += coord.Vec[i]
			}
			centroid.Height += coord.Height
			centroid.Adjustment += coord.Adjustment // Aggregate adjustment
			centroid.Count++
		}

		if centroid.Count == 0 {
			continue
		}

		// Average the centroid components
		n := float64(centroid.Count)
		for i := range centroid.Vec {
			centroid.Vec[i] /= n
		}
		centroid.Height /= n
		centroid.Adjustment /= n

		// Create the centroid coordinate with all fields
		centroidCoord := &coordinate.Coordinate{
			Vec:        centroid.Vec,
			Height:     centroid.Height,
			Adjustment: centroid.Adjustment, // Include adjustment
		}

		// Calculate drift using the correct origin and centroid
		driftMs := calculateRTT(origin, centroidCoord)

		// Log centroid drift
		logger.Printf("DRIFT_DATA,time=%s,centroid_ms=%.2f\n",
			time.Now().Format(time.RFC3339), driftMs)
		fmt.Printf("Current centroid drift: %.2f ms\n", driftMs)
	}
}

// calculateRTT remains unchanged from your existing version
func calculateRTT(a, b *coordinate.Coordinate) float64 {
	if len(a.Vec) != len(b.Vec) {
		panic("dimensions aren't compatible")
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
