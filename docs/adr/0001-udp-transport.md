# ADR-0001: UDP transport for untethered sensing

- Status: Accepted
- Date: 2026-10-10

## Context
The sensor was USB-tethered, which blocks free movement and the future robot.
RuView streams CSI frames over UDP from the sensor to a server.

## Decision
The firmware mirrors every frame (same JSONL object) as one UDP datagram to a
configured `ip:port`, in addition to serial. Default port 5005. The host parses
datagrams with the existing `records.parse_line`, so serial and UDP share one
wire format. Credentials and destination are set at runtime via serial commands
(`join`, `udp`); nothing is stored in the repository.

## Consequences
- The board roams on a power bank while the laptop listens.
- UDP is lossy; the pipeline tolerates gaps (fingerprinting does not need every
  frame). Serial remains the reliable fallback and debug path.
- Large scan frames may fragment on LAN; acceptable for this workload.
