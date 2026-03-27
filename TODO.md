# Ideas

## Benefits

- not using too much abstractions but highly transparent, e.g., how message history is created
- baseline for model behavior changes over time

## Notes

- DNS server on kali-linux might be broken (100.100.100.100)
- maybe remove parallelization to make code simpler?
- 2026-03-27: why is it hallucinating so much (not anymore though, couple of hours later)

## Memory

- [ ] use JSON instead of table for transporting knowledge information?
- [ ] allow to remove/update findings, e.g., for invalid credentials
- [ ] add id to finding (and allow update/remove)
- [ ] finding: maybe add a simple COW structure
- [ ] maybe also add memory for failed attempts

## Trajectory

- [ ] enforce ptt rewriting every x turns
    - [ ] also actually remove prior history after compaction
- [ ] circuit-breaker: tell it to stop repeating the same command over-and-over again
