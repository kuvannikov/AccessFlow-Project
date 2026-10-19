.PHONY: up down logs ps

# Start the dev stack and wait until both services are healthy.
up:
	docker compose up -d --wait --wait-timeout 180

# Stop and remove containers and the network. Volumes (the data) are kept.
# Never add -v here: it deletes the database.
down:
	docker compose down

# Follow the logs of all services (stop with Ctrl+C).
logs:
	docker compose logs -f --tail=100

# Show the state of the services.
ps:
	docker compose ps
