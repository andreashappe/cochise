# next steps / TODO bis Rio

- [ ] implement trajectory compression based on used tokens
- [ ] retest replayer
- [ ] retest analysis tool -> should be able to count/show compromised accounts + tokens

## Memory

- [ ] use JSON instead of table for transporting knowledge information?
- [ ] finding: maybe add a simple COW structure (not using that yet)
- [ ] maybe also add memory for failed attempts

## Errorfixes

- [ ] if error with tool calling (e.g., wrong parameter, add an error message but do not die)
- [ ] currently fails if we get a response/message >= context-size

# Ideas

- should we focus on 500 loc? Or can we do more (600-ish)? benefit
    - more robust in face of errors
    - better results (e.g., history management)
- configurable compaction: do we need it? can be configured (maybe)
- maybe remove parallelization to make code simpler?
- agents are not really noting down findings, esp. not findings in the summary texts
    - maybe add an extra loop for that?
- summary often has an updated 'next-steps' plan, could we use that or is this automatically used anyways

## Benefits

- litellm allows easy to switch between LLM models
- not using too much abstractions but highly transparent, e.g., how message history is created
- baseline for model behavior changes over time
- idea with 'improve attack coverage' -> looks good starting with that prototype, we see lots of attacks, but sometimes attack stalls

### model results

- feels like they are over-depending on password-spraying now
    - only saw minimax using responder

- claude-4.6-opus: I think it compromised everything in 90 minutes (3 domains, 4-5 server) during it's only run
- gemini-3-flash-preview: unstable, sometimes gets one domain, sometimes gets 2
- gpt-5.4: simlar to gemini, died due to context size (single message)

The new 'common' attack path is 'as-rep -> cracking -> ADCS -> dump credentials'

- chinese models seem simliar (like one year behnd US models):
    - glm-5-turbo
    - deepseek-v3.2 (only usable open-weight model)
        - glm-5 also looks kinda good, but many time-out commands (very similar)
    - xiaomi/mimi-v2-pro
    - minimax-m2.7: different attack traces, but included config files, responder, etc.
        - maybe not a full domain compromise, but really good as second model

- gpt-oss-120b: very struggling, worse than the rest
- qwen3.5-397b-a17b: died almost instantly due to a parameter error