---
name: tour-plan-skill
description: plan a tour based on known travel plan and output completed travel plan in JSON format
---

# tourism skills

tourism is considered as sequense of time-location pair sequences(linked list).

We extend the basic time-location pair as trvel node, which include type and details fields.

travel can be classified as different types:

* transportation: bus, train, flight, car rental, taxi, bike rental, walking...
* stay
  * accommodation: hotel, hostel, vacation rental, camping...
  * attraction: museum, park, historical site, event, restaurant, airport...
    * usually stay at a location for a period of time

Travel node should follow this format:

* time is represented by ISO 8601 format.
* start_time <= end_time (always)
* for stay nodes, start_location == end_location
* for transportation nodes, start_location != end_location
* locations should be as specific as possible, including city, district, address if possible.
* If tourism plan is **completed**, adjacent travel nodes should satisfy:
  * node_prev.end_time == node_curr.start_time
    * node_curr.end_time == node_next.start_time
    * locantions between adjacent nodes fullfill space continuity
  * transportation node and stay nodes should interleave
    * e.g. transportation -> stay/attraction -> transportation -> stay/accommodation -> ...

Following is an example of travel node sequence in JSON format:

```json
[
    {
        "type": "transportation",
        "start_time": "2023-10-01T07:00:00+08:00",
        "end_time": "2023-10-01T08:00:00+08:00",
        "start_location": "Kaohsiung, Taiwan",
        "end_location": "Kaohsiung International Airport(Xiaogang Airport), Kaohsiung, Taiwan",
        "details": "In car, go to airport"
    },
    {
        "type": "stay/attraction",
        "start_time": "2023-10-01T08:00:00+08:00",
        "end_time": "2023-10-01T09:00:00+08:00",
        "start_location": "Kaohsiung International Airport(Xiaogang Airport), Kaohsiung, Taiwan",
        "end_location": "Kaohsiung International Airport(Xiaogang Airport), Kaohsiung, Taiwan",
        "details": "Check-in and security check"
    },
    {
        "type": "transportation",
        "start_time": "2023-10-01T09:00:00+08:00",
        "end_time": "2023-10-01T11:00:00+08:00",
        "start_location": "Kaohsiung International Airport(Xiaogang Airport), Kaohsiung, Taiwan",
        "end_location": "Tokyo International Airport(Haneda Airport), Tokyo, Japan",
        "details": "Flight CI100"
    },
    {
        "type": "stay/accommodation",
        "start_time": "2023-10-01T12:00:00+09:00",
        "end_time": "2023-10-05T12:00:00+09:00",
        "start_location": "Tokyo Hotel, Tokyo, Japan",
        "end_location": "Tokyo Hotel, Tokyo, Japan",
        "details": "Check-in at Tokyo Hotel"
    },
    {
        "type": "stay/attraction",
        "start_time": "2023-10-02T10:00:00+09:00",
        "end_time": "2023-10-02T17:00:00+09:00",
        "start_location": "Tokyo Disneyland, Tokyo, Japan",
        "end_location": "Tokyo Disneyland, Tokyo, Japan",
        "details": "Visit Tokyo Disneyland"
    }
    // ...
]
```

1. User will provide some known travel plan, and ask the agent to help complete the travel plan.
2. Agent should convert the known travel plan into travel nodes sequence first. And this sequence is the initial input of iterative travel plan completion.
3. iterative travel plan completion:
   1. Agent analyze the current travel plan, and find the incomplete or ambiguous parts.
   2. Agent suggest possible travel nodes to complete the travel plan.
   3. User can accept or reject the suggested travel nodes, or provide additional information.
      * Agent should ask user question for more information if the travel plan is incomplete or ambiguous.
   4. Repeat until the travel plan is complete.
4. output the completed travel plan in JSON format file.

Agent can add additional fields to remember user thoughts of specific travel nodes, e.g.

```json
[
    {
        "type": "transportation",
        "start_time": "2023-10-01T07:00:00+08:00",
        "end_time": "2023-10-01T08:00:00+08:00",
        "start_location": "Kaohsiung, Taiwan",
        "end_location": "Kaohsiung International Airport(Xiaogang Airport), Kaohsiung, Taiwan",
        "details": "In car, go to airport",
        "cheat_sheet_": "provided by user at initial, but user can accept public transport too"
    },
    // ...
]
```

This way, agent can modify the travel plan based on user preferences.

## tips to suggest travel plan

* 2~3 attractions per day
* TSP(Traveling Salesman Problem) route optimization
* Between 10PM~8AM, 7~8hr rest time
