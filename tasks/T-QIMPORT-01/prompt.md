Build a small HTTP service that keeps a directory of contacts and can import contacts from an XML document, using Java 21 and the Quarkus project skeleton that is already in this repository.

It is built with `./mvnw package` and started as

```
java -Dquarkus.http.host=127.0.0.1 -Dquarkus.http.port=PORT -Dcontacts.data-dir=DIR -jar target/quarkus-app/quarkus-run.jar
```

It listens on 127.0.0.1 at PORT and stores its data under the directory DIR (creating it if needed), so that contacts survive a restart. When `contacts.data-dir` is not given, DIR is `./data`.

A contact has a `name`, an `email`, and optionally a `phone` and a `company`:

- `name`: a string of 1 to 100 characters.
- `email`: a string of at most 254 characters that contains exactly one `@`, with at least one character before it and, after it, a domain that contains at least one `.` and no spaces. No two contacts may have the same email.
- `phone` (optional): a string of 1 to 30 characters, each a digit, a space, `+`, `-`, `(` or `)`.
- `company` (optional): a string of 1 to 100 characters.

API (request and response bodies are JSON, except for the import document):

- `POST /contacts` with a body such as `{"name": "Ada Lovelace", "email": "ada@example.com", "phone": "+44 20 7946 0000"}` creates a contact and responds `201` with it. A contact is returned as `{"id": ..., "name": ..., "email": ..., "phone": ..., "company": ...}`, with `null` for an optional field that has no value. An email that another contact already has gets `409`.
- `GET /contacts/{id}` responds `200` with the contact. `DELETE /contacts/{id}` deletes it and responds `204`.
- `GET /contacts` responds `200` with `{"contacts": [...]}`, all contacts ordered by name (contacts with the same name in the order they were added). With the optional query parameter `q`, only contacts whose name, email or company contains `q`, ignoring case, are listed.
- `POST /contacts/import` with the header `Content-Type: application/xml` and a body such as

  ```xml
  <contacts>
    <contact>
      <name>Ada Lovelace</name>
      <email>ada@example.com</email>
      <phone>+44 20 7946 0000</phone>
    </contact>
    <contact>
      <name>Grace Hopper</name>
      <email>grace@example.com</email>
      <company>US Navy</company>
    </contact>
  </contacts>
  ```

  imports all the contacts in the document at once. The root element is `contacts`, and each of its child elements is a `contact` holding `name`, `email`, `phone` and `company` elements, of which `phone` and `company` may be left out. If every contact is valid by the rules above (an email may repeat neither one already stored nor one earlier in the document), all of them are added and the response is `200` with `{"imported": N}`, N being the number added. Otherwise none is added and the response is `400`, with an error message that contains `contact K`, where K is the position (counting from 1) of the first invalid contact. A body that is not well-formed XML, or does not have the structure above, gets `400`. A body larger than 1,048,576 bytes gets `413`.

Errors: a JSON body that is not valid JSON, or a missing or invalid field, gets `400`; an unknown contact gets `404`, as does any other path. Every error response has a JSON body of the form `{"error": "<message>"}`.

Use Java 21, the Quarkus version in the skeleton's `pom.xml` (3.40.1.1), and only the libraries already declared there. Do not change the build or start commands above.

Examples, with the service started on port 8765 and `ada.xml` holding the document above:

```
$ curl -s -X POST 127.0.0.1:8765/contacts/import -H 'Content-Type: application/xml' --data-binary @ada.xml
{"imported": 2}                                                          <- status 200
$ curl -s 127.0.0.1:8765/contacts
{"contacts": [{"id": ..., "name": "Ada Lovelace", ...}, {"id": ..., "name": "Grace Hopper", ...}]}    <- status 200
$ curl -s -o /dev/null -w '%{http_code}\n' -X POST 127.0.0.1:8765/contacts -H 'Content-Type: application/json' -d '{"name": "Ada", "email": "ada@example.com"}'
409
```
