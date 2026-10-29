Build a small HTTP service that keeps named counters, using Java 21 and the Quarkus project skeleton that is already in this repository.

It is built with `./mvnw package` and started as

```
java -Dquarkus.http.host=127.0.0.1 -Dquarkus.http.port=PORT -Dcounters.data-dir=DIR -jar target/quarkus-app/quarkus-run.jar
```

It listens on 127.0.0.1 at PORT and stores its data under the directory DIR (creating it if needed), so that counters survive a restart. When `counters.data-dir` is not given, DIR is `./data`.

API (response bodies are JSON):

- `POST /counters/{name}/increment` adds 1 to the counter called `name`, creating it with the value 0 first if it does not exist yet, and responds `200` with `{"name": ..., "value": N}`, N being the new value.
- `GET /counters/{name}` responds `200` with `{"name": ..., "value": N}`, or `404` if the counter does not exist.
- A counter name is 1 to 40 characters, each a lowercase letter, a digit or `-`. Any other name gets `400`.

Errors: an unknown counter gets `404`, as does any other path. Every error response has a JSON body of the form `{"error": "<message>"}`.

Use Java 21, the Quarkus version in the skeleton's `pom.xml` (3.40.1.1), and only the libraries already declared there. Do not change the build or start commands above.

Examples, with the service started on port 8765:

```
$ curl -s -X POST 127.0.0.1:8765/counters/visits/increment
{"name": "visits", "value": 1}                                           <- status 200
$ curl -s 127.0.0.1:8765/counters/visits
{"name": "visits", "value": 1}                                           <- status 200
$ curl -s -o /dev/null -w '%{http_code}\n' 127.0.0.1:8765/counters/Bad_Name
400
```
