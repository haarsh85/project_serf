package main

import (
	"encoding/json"
	"fmt"
	"log"
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
	serfAddress := "127.0.0.1:7373" // Replace with your Serf agent's address
	conn, err := net.Dial("tcp", serfAddress)
	if err != nil {
		log.Fatalf("Failed to connect to Serf RPC server: %v", err)
	}
	defer conn.Close()

	// Create a new encoder and decoder
	encoder := msgpack.NewEncoder(conn)
	decoder := msgpack.NewDecoder(conn)

	// Step 1: Send Handshake Header
	header := RPCHeader{Command: "handshake", Seq: 0}
	if err := encoder.Encode(header); err != nil {
		log.Fatalf("Failed to send handshake header: %v", err)
	}
	fmt.Println("Sent handshake header:", header)

	// Step 2: Send Handshake Body
	body := struct {
		Version int `msgpack:"Version"`
	}{Version: 1}
	if err := encoder.Encode(body); err != nil {
		log.Fatalf("Failed to send handshake body: %v", err)
	}
	fmt.Println("Sent handshake body:", body)

	// Step 3: Read Handshake Response
	var handshakeResponse map[string]interface{}
	if err := decoder.Decode(&handshakeResponse); err != nil {
		log.Fatalf("Failed to decode handshake response: %v", err)
	}
	fmt.Printf("Received handshake response: %+v\n", handshakeResponse)

	if errMsg, exists := handshakeResponse["Error"]; exists && errMsg != "" {
		log.Fatalf("Handshake failed: %v", errMsg)
	} else {
		fmt.Println("Handshake successful")
	}

	// Step 4: Send Get-Coordinate Header
	getCoordHeader := RPCHeader{Command: "get-coordinate", Seq: 1}
	if err := encoder.Encode(getCoordHeader); err != nil {
		log.Fatalf("Failed to send get-coordinate header: %v", err)
	}
	fmt.Println("Sent get-coordinate header:", getCoordHeader)

	// Step 5: Send Get-Coordinate Body (request)
	nodeRequest := struct {
		Node string `msgpack:"Node"`
	}{
		Node: "clab-century-serf5", // Replace with your node name
	}
	if err := encoder.Encode(nodeRequest); err != nil {
		log.Fatalf("Failed to send get-coordinate body: %v", err)
	}
	fmt.Printf("Sent get-coordinate body: %+v\n", nodeRequest)

	// Step 6: Read Get-Coordinate Response (Header + Body)
	// First, decode the header
	var getCoordHeaderResponse map[string]interface{}
	if err := decoder.Decode(&getCoordHeaderResponse); err != nil {
		log.Fatalf("Failed to decode get-coordinate response header: %v", err)
	}
	fmt.Printf("Decoded get-coordinate header: %+v\n", getCoordHeaderResponse)

	// Check for errors in the header
	if errMsg, exists := getCoordHeaderResponse["Error"]; exists && errMsg != "" {
		log.Fatalf("Get-coordinate command failed: %v", errMsg)
	}

	// Next, decode the body
	var getCoordBody map[string]interface{}
	if err := decoder.Decode(&getCoordBody); err != nil {
		log.Fatalf("Failed to decode get-coordinate response body: %v", err)
	}

	// Format the response body to JSON for readability
	prettyJSON, err := json.MarshalIndent(getCoordBody, "", "    ")
	if err != nil {
		log.Fatalf("Failed to format get-coordinate response body: %v", err)
	}
	fmt.Println("Decoded get-coordinate body (formatted):")
	fmt.Println(string(prettyJSON))

	// Final confirmation
	fmt.Println("Get-coordinate response fully received. Exiting program.")
}
