package main

import (
	"log"
	"os"
	"time"

	"github.com/hashicorp/serf/client"
	"github.com/hashicorp/serf/coordinate"
)

const (
	serfRPCAddr  = "127.0.0.1:7373"
	samplePeriod = 1 * time.Minute
)

func main() {
	// 1. Initialize logging
	nodeLogFile, err := os.OpenFile("serf_node_drift.log", os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		log.Fatal(err)
	}
	defer nodeLogFile.Close()
	nodeLogger := log.New(nodeLogFile, "", log.LstdFlags)

	systemLogFile, err := os.OpenFile("serf_system_drift.log", os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		log.Fatal(err)
	}
	defer systemLogFile.Close()
	systemLogger := log.New(systemLogFile, "", log.LstdFlags)

	// 2. Connect to Serf
	serfClient, err := client.ClientFromConfig(&client.Config{Addr: serfRPCAddr})
	if err != nil {
		log.Fatal(err)
	}
	defer serfClient.Close()

	// 3. Create origin coordinate EXACTLY as Serf does internally
	config := coordinate.DefaultConfig()
	origin := coordinate.NewCoordinate(config)
	for i := range origin.Vec {
		origin.Vec[i] = 0.0 // Maintain Serf's origin Height (config.HeightMin)
	}
	origin.Adjustment = 0.0

	// 4. Main monitoring loop
	ticker := time.NewTicker(samplePeriod)
	defer ticker.Stop()

	for range ticker.C {
		members, err := serfClient.Members()
		if err != nil {
			log.Printf("Member error: %v", err)
			continue
		}

		var (
			maxDrift    float64
			totalDrift  float64
			activeNodes int
			vecSum      = make([]float64, config.Dimensionality)
			heightSum   float64
			adjustSum   float64
		)

		for _, member := range members {
			if member.Status != "alive" {
				continue
			}

			coord, err := serfClient.GetCoordinate(member.Name)
			if err != nil || coord == nil {
				continue
			}

			// 5. Calculate TRUE drift using Serf's actual method
			drift := coord.DistanceTo(origin).Seconds() * 1000 // ms

			// Log individual node drift
			nodeLogger.Printf("NODE_DRIFT node=%s drift_ms=%.2f vec=%v height=%.6f adj=%.6f",
				member.Name, drift, coord.Vec, coord.Height, coord.Adjustment)

			// Update metrics
			if drift > maxDrift {
				maxDrift = drift
			}
			totalDrift += drift
			activeNodes++

			// Accumulate components for true centroid calculation
			for i := range coord.Vec {
				vecSum[i] += coord.Vec[i]
			}
			heightSum += coord.Height
			adjustSum += coord.Adjustment
		}

		// 6. Calculate system metrics
		if activeNodes > 0 {
			n := float64(activeNodes)
			avgDrift := totalDrift / n

			// Calculate TRUE centroid including all components
			centroidVec := make([]float64, config.Dimensionality)
			for i := range vecSum {
				centroidVec[i] = vecSum[i] / n
			}
			centroidHeight := heightSum / n
			centroidAdjust := adjustSum / n

			// Construct centroid coordinate EXACTLY like real nodes
			centroidCoord := &coordinate.Coordinate{
				Vec:        centroidVec,
				Height:     centroidHeight,
				Adjustment: centroidAdjust,
				Error:      config.VivaldiErrorMax, // Not used in drift calc
			}

			// Calculate centroid drift using Serf's actual distance method
			centroidDrift := centroidCoord.DistanceTo(origin).Seconds() * 1000

			// Log metrics
			systemLogger.Printf("SYSTEM_DRIFT nodes=%d max_ms=%.2f avg_ms=%.2f centroid_ms=%.2f",
				activeNodes, maxDrift, avgDrift, centroidDrift)
		}
	}
}
