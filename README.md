# bbcelection-hue

Drives a set of Philips Hue lights to react to election night declarations from the BBC.
A random constituency page is polled every second to see if its declared yet. If it has,
its result is parsed and added to a queue of declarations. Periodically, this queue is popped
and used to animate the lights with the result from that seat - briefly showing the colour of the
old party dimly, then the new party brightly. These colours are defined in the 'colors' dict and
aren't exhaustive for all minor parties, but are based on the BBC's colour scheme. When there are
no declarations, three lights are used to show the relative strength of Labour, Conservatives, and the
SNP. This is built with three lights in mind but state_of_the_parties() can be tweaked for other effects.

seat_ids.json is included with a mapping of seat names to IDs used by the BBC correct as
of June 2017, but re-run get_constituency_ids() to update this if necessary.

NOTE! This is very brittle, and was thrown together on election night to get something working!
For example, note that the BRIDGE_IP and light ids in LIGHTS are based on my setup and need to be updated for your own.
In the event of another election, the xpaths would probably need to be tweaked but the main plumbing should
still work.

## Acknowledgements
This includes [hue-python-rgb-converter](https://github.com/benknight/hue-python-rgb-converter) under an MIT License,
for converting RGB colours to the lights' colour space.