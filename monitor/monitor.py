import pandas as pd
import time
from prometheus_client.parser import text_string_to_metric_families
import requests
from datetime import datetime
from prophet import Prophet
from prometheus_client import start_http_server,Gauge
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error
import numpy as np
import argparse
import json

parser = argparse.ArgumentParser(description='Monitor application for Boutique services.')
parser.add_argument('--service1', type=str, help='Name of the source service')
parser.add_argument('--service2', type=str, help='Name of the destination service')
parser.add_argument('--training_data_file', type=str, help='Path to the training data file')
parser.add_argument('--prometheus_port', type=int, default=8080, help='Port for Prometheus scraping')

args = parser.parse_args()

service1 = args.service1
service2 = args.service2
training_data_file = args.training_data_file

prometheus_url = "http://34.18.73.118:9090/api/v1/query"


# Replace with your Prometheus server URL
# prometheus_url = "http://prometheus.istio-system:9090/api/v1/query"

# prometheus_url = "http://34.18.73.118:9090/api/v1/query"

# Number of minutes to pull data for each iteration
minutes_to_pull = 1

anomaly_count_gauge = Gauge('lab7_{}_to_{}_anomaly_count'.format(service1, service2), 'Anomaly count in the monitoring application')
mae_gauge = Gauge('lab7_{}_to_{}_mae'.format(service1, service2), 'mean absolute error in requests')
mape_gauge = Gauge('lab7_{}_to_{}_mape'.format(service1, service2), 'mean absolute percentage error in requests')
y_min_gauge = Gauge('lab7_{}_to_{}_y_min'.format(service1, service2), 'minimum request time')
y_gauge = Gauge('lab7_{}_to_{}_y'.format(service1, service2), 'actual request time')
y_max_gauge = Gauge('lab7_{}_to_{}_y_max'.format(service1, service2), 'maximum request time')
# query  histogram quantile

query_5 = "histogram_quantile(0.5, sum by (le) (rate(istio_request_duration_milliseconds_bucket{{app='{}', destination_app='{}', reporter='source'}}[1m])))".format(service1, service2)
query_95 = "histogram_quantile(0.95, sum by (le) (rate(istio_request_duration_milliseconds_bucket{{app='{}', destination_app='{}', reporter='source'}}[1m])))".format(service1, service2)


r = requests.get(prometheus_url, params={"query": query_5})
response_data = r.json()

with open('boutique_training.json', 'r') as f:
    training_data = json.load(f)


# Create dataframe
# df_train = pd.DataFrame( ['data']['result'][0]['values'] )
df_train = pd.DataFrame(training_data['data']['result'][0]['values'])
df_train.columns = ['ds', 'y']
df_train['ds'] = pd.to_datetime(df_train['ds'], unit='s')
df_train['y'] = df_train['y'].astype(float)

# Create Prophet model
model = Prophet(interval_width=0.99,
    yearly_seasonality=False,
    weekly_seasonality=False,
    daily_seasonality=False,
    growth='flat')
model.add_seasonality(name='hourly', period=1/24, fourier_order=5)

model.fit(df_train)
# Initialize anomaly count
total_anomalies = 0

results_df = pd.DataFrame(columns=['Timestamp', 'Anomalies', 'MAE', 'MAPE'])

# Start Prometheus client
start_http_server(args.prometheus_port)

# Start the monitoring loop
while True:
 
    # Wait for the specified number of minutes
    time.sleep(1 * minutes_to_pull)

    # Fetch the latest request time
    r = requests.get(prometheus_url, params={"query": query_5})
    response_data = r.json()

    # print(response_data)

    # Extract the latest request time
    latest_request_time = response_data['data']['result'][0]['value'][0]
    latest_request_y = response_data['data']['result'][0]['value'][1]
    # print(latest_request_y)

    if latest_request_y =='NaN':
        continue

    # Convert the latest request time to datetime
    latest_request_datetime = datetime.utcfromtimestamp(float(latest_request_time))

    # Calculate the time shift delta
    test_delta = pd.to_timedelta(df_train['ds'].iloc[0] - latest_request_datetime)

    # Create a DataFrame for the latest request time
    test_df = pd.DataFrame({'ds': [latest_request_time]})
    test_df['y'] = latest_request_y
    # print(test_df)
    # Convert the 'ds' column to datetime
    test_df['ds'] = pd.to_datetime(test_df['ds'], unit='s')

    test_df['ds'] = test_df['ds'] - test_delta

    # Forecast the request time
    forecast = model.predict(test_df)

    # Merge actual and predicted values
    performance = pd.merge(test_df, forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']], on='ds')
    

    # convert to float
    performance['y'] = performance['y'].astype(float)
    # replace nan with mean
    performance['y'] = performance['y'].fillna(performance['y'].mean())



    # Check MAE value
    performance_MAE = mean_absolute_error(performance['y'], performance['yhat'])
    # print(f'The MAE for the model is {performance_MAE}')

    # Check MAPE value
    performance_MAPE = mean_absolute_percentage_error(performance['y'], performance['yhat'])
    # print(f'The MAPE for the model is {performance_MAPE}')

    performance['anomaly'] = performance.apply(lambda rows: 1 if ((float(rows.y)<rows.yhat_lower)|(float(rows.y)>rows.yhat_upper)) else 0, axis = 1)

    # Take a look at the anomalies
    anomalies = performance[performance['anomaly']==1].sort_values(by='ds')
    # print(anomalies)

    # Calculate the total number of anomalies
    anomaly = len(anomalies)

    # Update anomaly count gauge
    anomaly_count_gauge.set(anomaly)

    
    # Update MAE and MAPE gauges
    mae_gauge.set(performance_MAE)
    mape_gauge.set(performance_MAPE)

    # Update y_min, y, and y_max gauges
    y_min_gauge.set(performance['yhat_lower'].iloc[0])
    y_gauge.set(performance['yhat'].iloc[0])
    y_max_gauge.set(performance['yhat_upper'].iloc[0])


    # Append the results to the DataFrame
    results_df = pd.concat([results_df, pd.DataFrame({
        'Timestamp': [latest_request_datetime],
        'Anomalies': [anomaly],
        'MAE': [performance_MAE],
        'MAPE': [performance_MAPE]
    })], ignore_index=True)


    # Print the current last 30 results_df
    print(results_df.tail(30))


