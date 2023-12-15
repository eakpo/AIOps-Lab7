import time
import requests
from prometheus_client import start_http_server, Gauge

prometheus_url = "http://prometheus.istio-system:9090/api/v1/query"

# prometheus_url = "http://34.18.73.118:9090/api/v1/query"

incident_temperature_gauge = Gauge('lab7_incident_temperature', 'Incident temperature in the monitoring application')
sev1_gauge = Gauge('lab7_frontend_to_cartservice_sev1', 'Sev1 incident count in the monitoring application')
sev2_gauge = Gauge('lab7_checkoutservice_to_paymentservice_sev2', 'Sev2 incident count in the monitoring application')

# Query anomaly metrics from monitor application
query_sev1 = "lab7_frontend_to_cartservice_anomaly_count"
query_sev2 = "lab7_checkoutservice_to_paymentservice_anomaly_count"

# Define constants
incident_threshold = 10

# Initialize accumulators
accumulator_service1 = 0
accumulator_service2 = 0

def fetch_anomaly_count(query):
    try:
        response = requests.get(prometheus_url, params={"query": query})
        response.raise_for_status()
        response_data = response.json()
        anomaly_count = int(response_data['data']['result'][0]['value'][1])
        return anomaly_count
    except Exception as e:
        print(f"Error fetching anomaly count: {e}")
        return 0

def detect_incident():
    global accumulator_service1, accumulator_service2

    # Fetch anomaly count
    sev1_count = fetch_anomaly_count(query_sev1)
    sev2_count = fetch_anomaly_count(query_sev2)

    # Update 
    # if anomaly detected, increment by the anomaly count
    # If no anomaly detected, decrement by the specified 2, but never go below zero
    if sev1_count > 0:
        accumulator_service1 += sev1_count
    else:
        accumulator_service1 = max(0, accumulator_service1 - 2)

    if sev2_count > 0:
        accumulator_service2 += sev2_count
    else:
        accumulator_service2 = max(0, accumulator_service2 - 2)

    # Calculate incident temperature
    incident_temperature = accumulator_service1 + accumulator_service2

    # Update incident temp gauge
    incident_temperature_gauge.set(incident_temperature)

    # Check if incident is detected
    if incident_temperature > incident_threshold:
        # Declare incident severity
        if accumulator_service1 > incident_threshold and accumulator_service2 > incident_threshold:
            severity = "Sev 1"
            # set sev1 gauge to 1 and sev2 gauge to 0
            sev1_gauge.set(1)
            sev2_gauge.set(0)
        elif accumulator_service1 > incident_threshold or accumulator_service2 > incident_threshold:
            severity = "Sev 2"
            # set sev1 gauge to 0 and sev2 gauge to 1
            sev1_gauge.set(0)
            sev2_gauge.set(1)
        else:
            severity = "No incident severity"
            # set both gauges to 0
            sev1_gauge.set(0)
            sev2_gauge.set(0)

        # Print incident details
        print(f"Incident detected! Severity: {severity}")
        # return True
    else:
        print("No incident detected")
        # return False
        
    
        


# Start Prometheus client
start_http_server(8083)

# Start the monitoring loop
while True:
    detect_incident()
    time.sleep(20)
