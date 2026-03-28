# Ideas

- should we focus on 500 loc? Or can we do more (600-ish)? benefit
    - more robust in face of errors
    - better results (e.g., history management)
- configurable compaction: do we need it? can be configured (maybe)

## Benefits

- not using too much abstractions but highly transparent, e.g., how message history is created
- baseline for model behavior changes over time

## Notes

- maybe remove parallelization to make code simpler?
- 2026-03-27: why is it hallucinating so much (not anymore though, couple of hours later) -> maybe problem with tool integration
- agents are not really noting down findings, esp. not findings in the summary texts
    - maybe add an extra loop for that?
- feels like they are over-depending on password-spraying now
    - only saw minimax using responder
- summary often has an updated 'next-steps' plan, could we use that or is this automatically used anyways

### model results

- claude-4.6-opus: I think it compromised everything in 90 minutes (3 domains, 4-5 server) during it's only run
- gemini-3-flash-preview: unstable, sometimes gets one domain, sometimes gets 2
- gpt-5.4: simlar to gemini, died due to context size (single message)

The new 'common' attack path is 'as-rep -> cracking -> ADCS -> dump credentials'

- chinese models seem simliar (like one year behnd US models):
    - glm-5-turbo
    - deepseek-v3.2 (only usable closed-source model)
    - xiaomi/mimi-v2-pro
    - minimax-m2.7: different attack traces, but included config files, responder, etc.
        - maybe not a full domain compromise, but really good as second model

- gpt-oss-120b: very struggling, worse than the rest
- qwen3.5-397b-a17b: died almost instantly due to a parameter erro

## Memory

- [ ] use JSON instead of table for transporting knowledge information?
- [x] allow to remove/update findings, e.g., for invalid credentials
- [x] add id to finding (and allow update/remove)
- [ ] finding: maybe add a simple COW structure (not using that yet)
- [ ] maybe also add memory for failed attempts

## Output / Logs

- [ ] verify that we still have good JSON-based logs
    - [ ] check replay tool
    - [ ] check analysis tool
- [ ] maybe also create text-based logs?

## Errorfixes

- [ ] if error with tool calling (e.g., wrong parameter, add an error message but do not die)

## Trajectory

- [x] enforce ptt rewriting every x turns
    - [ ] also actually remove prior history after compaction
- [ ] circuit-breaker: tell it to stop repeating the same command over-and-over again
