# The Summoner Platform SDK
**Everything you need to build a cross-enterprise ready multi-Agent system.**

```
 _______           _        _       
(  ____ \|\     /|( \      ( \      
| (    \/| )   ( || (      | (      
| (__    | |   | || |      | |      
|  __)   | |   | || |      | |      
| (      | |   | || |      | |      
| )      | (___) || (____/\| (____/\
|/       (_______)(_______/(_______/
                                    
 _______  _______  ______   _______ 
(  ____ \(  ___  )(  __  \ (  ____ \
| (    \/| (   ) || (  \  )| (    \/
| |      | |   | || |   ) || (__    
| |      | |   | || |   | ||  __)   
| |      | |   | || |   ) || (      
| (____/\| (___) || (__/  )| (____/\
(_______/(_______)(______/ (_______/
                                    
 _       _________ _______  _______ 
( \      \__   __/(  ____ \(  ____ \
| (         ) (   | (    \/| (    \/
| |         | |   | (__    | (__    
| |         | |   |  __)   |  __)   
| |         | |   | (      | (      
| (____/\___) (___| )      | (____/\
(_______/\_______/|/       (_______/
                                                           
```

---

**Summoner is not a typical platform.** We have specifically engineered it, with great discipline, so that you (the developer) can clone our stack and run it locally. You will be running and testing your multi-agent system in the equivalent of a full production environment, so that you can deploy with confidence.

**Still not confident?** That's fine: we have a _[staging environment](https://staging.summoner.org)_ where you can deploy your agents and witness them working in the cloud with all the associated latency and connectivity required to do that. However, in order to utilize the staging environment you will need to develop your agent under the same strict discipline that made the platform possible: absolutely zero extra imports beyond the standard Python SDK are allowed.

---

# 1. Start by cloning and running our full stack.
Visit the `frontend` [here](https://github.com/Summoner-Network/frontend) and follow the instructions in the README. If you run the server, and it prints that all self-tests have passed, then congratulations! You know for a fact that our code is working perfectly in your local environment. If it is not working, let us know in the [Discord](https://discord.gg/AAYuyThmsw) server. We will get it rectified so that you may continue making progress. _It should always just work!_

---

# 2. Continue by cloning this repository.
Leave the stack running. It is happy to do work and have things thrown at it no problem, you shouldn't need to touch it. If you do decide to touch it for good reasons, please open an issue to contribute to the `frontend` repository so that we can absorb your helpful contribution.

This repository contains everything you need to develop agents within the platform, alongside the platform itself (which you have running locally)!

---

# 3. What is an Agent?

"Wow, that is an excellent question!" Summoner's platform definition of an Agent is a class that implements the following contract (pseudocode):

```python
# Implemented by the developer
await agent.init(script_config, shard_config)
while True: # Managed by the platform
  # Implemented by the developer
  await agent.work()
  # Managed by the platform
  await sleep(script_config["system"]["core"]["maxSleepMs"])
```

As you can see, the platform's job is to ensure a couple of non-trivial things:
- `init` is only called once per worker / shard instance.
- Only one instance of a shard is "working" at any given time.
- The `work` function is called _as frequently as the "max sleep" allows_ (may be 0).
  - Note that this is the MAX SLEEP, not a guarunteed sleep. It is not possible for the platform to guaruntee a fixed period of sleep, because it is a distributed fleet of _replicated_ workers, not a single worker.
  - If one worker fails, another immediately takes over by following the above routine. There is no complicated coordination: there is a perpetual [livelock](https://stackoverflow.com/questions/6155951/whats-the-difference-between-deadlock-and-livelock) ("logjam") to run the agent across the whole fleet.

This simplicity guaruntees that our platform is capable of upholding its end of the bargain at scale and under pressure. It also allows you, dear developer, to build tremendous things without our substantial help.