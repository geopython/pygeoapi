# bootstrap the teamengine service
# 1. ensure service is up
# 2. register a test user for running tests

user_registration_curl_command=$(
    printf '%s' \
    "curl -v " \
    "--silent " \
    "--output /dev/null " \
    "--write-out '%{http_code}' " \
    "--data firstName=teamengine " \
    "--data lastName=user " \
    "--data username=teamengine " \
    "--data password=tester " \
    "--data repeat_password=tester " \
    "--data email=noone@noplace.com " \
    "--data organization=none " \
    "--data acceptPrivacy=on " \
    "--data disclaimer=on " \
    "http://localhost:8080/teamengine/registrationHandler"
)
response_status=$(docker exec pygeoapi-cite-teamengine-1 \
    bash -c 'curl --silent --output /dev/null --write-out "%{http_code}" localhost:8080/teamengine/') && \
echo "Response status: ${response_status}" && \
user_registration_response_status=$(docker exec pygeoapi-cite-teamengine-1 \
    bash -c "${user_registration_curl_command}") && \
echo "User registration status: ${user_registration_response_status}"
