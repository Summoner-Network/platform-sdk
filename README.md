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