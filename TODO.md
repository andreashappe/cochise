# next steps / TODO bis Rio

- [ ] if error with tool calling (e.g., wrong parameter, add an error message but do not die)
- [ ] currently fails if we get a response/message >= context-size
- [ ] the whole knowledge structure is ugly as hell
    - [ ] use JSON instead of table for transporting knowledge information?
    - [ ] finding: maybe add a simple COW structure (not using that yet)
    - [ ] maybe also add memory for failed attempts

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


> You're thinking of one of the most powerful scenes in Goethe's Faust I — the "Osternacht" (Easter Night) scene at the end of the study.
> Faust has reached absolute despair, convinced that all his scholarship has brought him no closer to understanding the world. He raises a vial of poison to his lips — and then the Easter bells ring out, accompanied by the choir singing "Christ ist erstanden." He doesn't drink.
> What's striking is why he puts the poison down. It's not faith — Faust explicitly says he doesn't believe the message anymore. It's the memory the bells trigger: childhood, the feeling of Easter morning, a time when the world still felt whole. It's pure affect, not theology. The bells don't convince him of anything; they just reconnect him to a version of himself that still wanted to be alive.
> There's a nice irony in the timing too — it's the moment of resurrection pulling him back from self-annihilation, but Faust's "resurrection" is entirely secular. Goethe gives the Christian framework and then hollows it out.

> Good question — it's actually not Easter Monday. The suicide scene happens on the night of Holy Saturday transitioning into Easter Sunday. The bells Faust hears are the Easter morning bells announcing the resurrection, ringing in Easter Sunday at dawn (or midnight, depending on how you read the staging).