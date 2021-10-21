# RLPytrade

Python script I wrote to make my life easier in the Rocket League trading community.

This script is in a very experimental/draft state, I probably won't touch it anymore.

All sensitive information has been replaced with `<removed>`.

I spent a lot of time working on this, sadly the script lacks of useful comments.

I'm not really used to Python, Pythonic lovers please be careful your eyes might cry.

To be able to use APIs of [RL Trading Post](https://play.google.com/store/apps/details?id=com.hintech.rltradingpost) and [RL Garage](https://play.google.com/store/apps/details?id=com.rocketleaguegarage.rlgarage) I used [apk-mitm](https://github.com/shroudedcode/apk-mitm) to intercept their encrypted traffic and understand how to use them.

Since RL Trading Post doesn't have a web version, automated scripts/bots are less common so it was a good playground.

Using this script I was able to create/delete/bump trade offers for both apps (a good trick is to delete then recreate a trade offer so you can bypass bump delay).

For RL Trading Post I could also filter items wanted/offered, I also made a local WebSocket server (using [SimpleWebSocketServer](https://github.com/dpallot/simple-websocket-server)) for it which sends filtered results in a web browser in a form of a simple table (the minimalistic stylesheet is based on [rl-trades](https://www.rl-trades.com/) one), from this table I could also directly send messages to the user on the app.

To be able to send PSN friend requests I looked into [psn-php](https://github.com/Tustin/psn-php) to understand how to use the PSN API.