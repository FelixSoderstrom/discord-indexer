After reviewing the state of configuration manager, I have decided a proper refactor is in place.

Instead of describing wverything that is wrong with the current implementation I will instead describe how it should be.


# context

We are creating a discord bot that can index messages from multiple servers.
Everything is running locally on consumer hardware.
One bot instance running (main.py on someones machine) should handle mutiple servers.
Each server requires its own config setup, hence the need of some sort of persistant storage.


# why the setup process is needed

When messages are fetches from the discord API they are places in a queue before processing.
In the events of a message giving an error in the message processing pipeline, we want to be able to exit gracefully.
The setup process lets the user of this bot determine the behaviour of the app when an error occurs. Do they want to skip the message? Do they want to close down the app?
Currenly, we only have one of those error but the plan is to make the configuration process modular enough so that we can just insert new errors here to be configured by the user.
This makes the app behave just like the user wants.


# What it should look like

The total flow of this setup process:
1. Monitor server_id on incoming messages by intercepting before pipeline
2. Enforce configuration process if server_id is not configured
3. Run configuration process
4. Store config persistently


## 1. Monitor server_id

After messages have been fetched by the discord api, we intercept them at the junction point before they enter the message processing pipeline.
We need to:
- Get the database session for our configurations SQLite database
- Get all server_ids from the configurations database (list in memory)
- Iterate over the messages and compare against the list.
- Trigger a function to run the config process (terminal UI) if a server_id was not found in the list


## 2. Enforce configuration process

If a messages server_id cannot be found in the list of servers we need to enforce the configuration process before this message gets processed iby the pipeline. We also need to halt all message behind it in the queue until the setup has been completed.
The process **NEEDS** to be synchronous so that all messages **STOP** when a new server is detected.
We also do **NOT** want multiple configuration processes for the same server.


## 3. Run configuration process

This is where Björns code can be reused I believe (although heavily refactored to remove all the overneigneered nonsense).
In this section we want a simple terminal UI that asks the question:
- How would you like the app to behave when a message fails being processed?
With these answers:
1. Skip that message and continue with others.
2. Stop the process and close down the app.

Most importantly this step needs to be created so that I can easily jsut add more questions in the UI, columns in the DB and so on..



## 4. Persistent storage of config

Each server should have their own configuration.
This can easily be separated as different rows in the database sorted by server_id as PK.
Tie this together with setup_db.py so that we can just get the configuration database session from there.


# Other thoughts

The current state overcomplicated this above proposed solution greatly.
To be honest, I dont even think this needs to be a class.
Whether this needs to be functional programming or object oriented I will leave up for discussion between me and Claude.

Wether to use a single SQLite database or several json files for storing persistent server-configurations, im also not completely sure of.
We have a solid system for handing out database sessions so integration would be seamless.
Json files allow for better insight and manual user-configuration.
This would essentially remove the need entirely for the change_settings.py script.
I will also leave this up for discussion between me and Claude.