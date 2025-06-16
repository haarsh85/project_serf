package main

import (
	"encoding/json"
	"fmt"
	"log"
	"math"
	"net"

	"github.com/vmihailenco/msgpack/v5"
)

// RPCHeader represents the header structure for RPC commands
type RPCHeader struct {
	Command string `msgpack:"Command"`
	Seq     int    `msgpack:"Seq"`
}

func main() {
	// Set up the connection to the Serf agent
	serfAddress := "127.0.0.1:7373" // RPC address
	conn, err := net.Dial("tcp", serfAddress)
	if err != nil {
		log.Fatalf("Failed to connect to Serf RPC server: %v", err)
	}
	defer conn.Close()

	// Create a new encoder and decoder
	encoder := msgpack.NewEncoder(conn)
	decoder := msgpack.NewDecoder(conn)

	// Step 1: Handshake
	handshake(encoder, decoder)

	// Step 2: Get Members
	memberNames := getMembers(encoder, decoder)

	// Step 3: Get Coordinates for All Members
	allCoordinates := make(map[string]interface{})
	for _, member := range memberNames {
		coordinate := getCoordinate(encoder, decoder, member)
		allCoordinates[member] = coordinate
	}

	// Step 4: Calculate RTTs
	rtts := calculateRTTs(allCoordinates)

	// Print pairwise RTTs
	prettyJSON, err := json.MarshalIndent(rtts, "", "    ")
	if err != nil {
		log.Fatalf("Failed to format RTTs: %v", err)
	}
	fmt.Println("Pairwise RTTs:")
	fmt.Println(string(prettyJSON))
}

// handshake performs the handshake operation with the Serf node.
func handshake(encoder *msgpack.Encoder, decoder *msgpack.Decoder) {
	// Send Handshake Header
	header := RPCHeader{Command: "handshake", Seq: 0}
	if err := encoder.Encode(header); err != nil {
		log.Fatalf("Failed to send handshake header: %v", err)
	}
	fmt.Println("Sent handshake header:", header)

	// Send Handshake Body
	body := struct {
		Version int `msgpack:"Version"`
	}{Version: 1}
	if err := encoder.Encode(body); err != nil {
		log.Fatalf("Failed to send handshake body: %v", err)
	}
	fmt.Println("Sent handshake body:", body)

	// Read Handshake Response
	var response map[string]interface{}
	if err := decoder.Decode(&response); err != nil {
		log.Fatalf("Failed to decode handshake response: %v", err)
	}
	fmt.Printf("Received handshake response: %+v\n", response)

	if errMsg, exists := response["Error"]; exists && errMsg != "" {
		log.Fatalf("Handshake failed: %v", errMsg)
	}
	fmt.Println("Handshake successful")
}

// getMembers fetches the list of all member names in the Serf cluster.
func getMembers(encoder *msgpack.Encoder, decoder *msgpack.Decoder) []string {
	// Send Members Header
	membersHeader := RPCHeader{Command: "members", Seq: 1}
	if err := encoder.Encode(membersHeader); err != nil {
		log.Fatalf("Failed to send members header: %v", err)
	}
	fmt.Println("Sent members header:", membersHeader)

	// Decode Members Response Header
	var membersHeaderResponse map[string]interface{}
	if err := decoder.Decode(&membersHeaderResponse); err != nil {
		log.Fatalf("Failed to decode members response header: %v", err)
	}
	fmt.Printf("Decoded members response header: %+v\n", membersHeaderResponse)

	// Decode Members Response Body
	var membersBody map[string]interface{}
	if err := decoder.Decode(&membersBody); err != nil {
		log.Fatalf("Failed to decode members response body: %v", err)
	}
	fmt.Println("Decoded members response body")

	// Extract Member Names
	var memberNames []string
	if members, exists := membersBody["Members"].([]interface{}); exists {
		for _, member := range members {
			if memberMap, ok := member.(map[string]interface{}); ok {
				if name, ok := memberMap["Name"].(string); ok {
					memberNames = append(memberNames, name)
				}
			}
		}
	}

	return memberNames
}

// getCoordinate fetches the coordinate of a specific node by its name.
func getCoordinate(encoder *msgpack.Encoder, decoder *msgpack.Decoder, nodeName string) map[string]interface{} {
	// Send Get-Coordinate Header
	getCoordHeader := RPCHeader{Command: "get-coordinate", Seq: 2}
	if err := encoder.Encode(getCoordHeader); err != nil {
		log.Fatalf("Failed to send get-coordinate header: %v", err)
	}
	fmt.Printf("Sent get-coordinate header for node: %s\n", nodeName)

	// Send Get-Coordinate Body
	nodeRequest := struct {
		Node string `msgpack:"Node"`
	}{
		Node: nodeName,
	}
	if err := encoder.Encode(nodeRequest); err != nil {
		log.Fatalf("Failed to send get-coordinate body: %v", err)
	}
	fmt.Printf("Sent get-coordinate body for node: %s\n", nodeName)

	// Decode Get-Coordinate Response Header
	var coordHeaderResponse map[string]interface{}
	if err := decoder.Decode(&coordHeaderResponse); err != nil {
		log.Fatalf("Failed to decode get-coordinate response header: %v", err)
	}
	fmt.Printf("Decoded get-coordinate response header for node: %s\n", nodeName)

	// Decode Get-Coordinate Response Body
	var coordBody map[string]interface{}
	if err := decoder.Decode(&coordBody); err != nil {
		log.Fatalf("Failed to decode get-coordinate response body: %v", err)
	}

	return coordBody
}

// calculateRTTs computes pairwise RTTs between all nodes.
func calculateRTTs(coordinates map[string]interface{}) map[string]map[string]float64 {
	rtts := make(map[string]map[string]float64)

	for nodeA, coordA := range coordinates {
		coordMapA := coordA.(map[string]interface{})["Coord"].(map[string]interface{})
		heightA := coordMapA["Height"].(float64)
		vecA := coordMapA["Vec"].([]interface{})
		adjustmentA := coordMapA["Adjustment"].(float64)

		for nodeB, coordB := range coordinates {
			if nodeA == nodeB {
				continue
			}

			coordMapB := coordB.(map[string]interface{})["Coord"].(map[string]interface{})
			heightB := coordMapB["Height"].(float64)
			vecB := coordMapB["Vec"].([]interface{})
			adjustmentB := coordMapB["Adjustment"].(float64)

			// Calculate Euclidean distance
			sumsq := 0.0
			for i := range vecA {
				diff := vecA[i].(float64) - vecB[i].(float64)
				sumsq += diff * diff
			}
			euclideanDistance := math.Sqrt(sumsq)

			// Calculate RTT
			baseRTT := euclideanDistance + heightA + heightB
			adjustedRTT := baseRTT + adjustmentA + adjustmentB
			finalRTT := adjustedRTT
			if adjustedRTT < 0 {
				finalRTT = baseRTT // Fallback to base RTT if adjustment is negative
			}

			// Convert RTT to milliseconds
			rttInMillis := finalRTT * 1000.0
			if _, exists := rtts[nodeA]; !exists {
				rtts[nodeA] = make(map[string]float64)
			}
			rtts[nodeA][nodeB] = rttInMillis

			// Debugging Output
			fmt.Printf("RTT from %s to %s: Euclidean=%.6f, Adjusted=%.6f, Final=%.6f ms\n",
				nodeA, nodeB, euclideanDistance, adjustedRTT, rttInMillis)
		}
	}

	return rtts
}
