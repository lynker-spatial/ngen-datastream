import boto3
import time, os

def wait_for_instance_running(instance_id):
    retries = 0
    while True:
        try:
            response = client_ec2.describe_instances(
            InstanceIds=[
                instance_id
            ]
            )
            if response['Reservations'][0]['Instances'][0]['State']['Name'] == "running":
                return True
            else:
                print(f"Instance is not yet running {response}")
            retries += 1            
        except:
            pass
        time.sleep(2 ** (0.5*retries))
    
def lambda_handler(event, context):

    t0 = time.time()
    event['t0'] = t0
    event['ii_s3_object_checked'] = False
    if not "timeout_s" in event['run_options']:
        print(f'Setting timeout_s to default 3600 seconds')
        event['run_options']['timeout_s'] = 3600

    if not "retry_attempt" in event:
        event['retry_attempt'] = 0
    else:
        event['retry_attempt'] += 1

    event['region'] = os.environ['AWS_REGION']
    global client_ec2
    client_ec2 = boto3.client('ec2',region_name=event['region'])

    event['instance_parameters']['MaxCount'] = 1
    event['instance_parameters']['MinCount'] = 1
    params             = event['instance_parameters']

    response           = client_ec2.run_instances(**params)
    instance_id        = response['Instances'][0]['InstanceId']

    while True:
        try:
            client_ec2.start_instances(InstanceIds=[instance_id])   
            break
        except:
            print(f'Tried running {instance_id}, failed. Trying again.')
            time.sleep(1)

    if not wait_for_instance_running(instance_id):
        raise Exception(f"EC2 instance {instance_id} did not reach 'Online' state")
    print(f'{instance_id} has been launched and running')

    event['instance_parameters']['InstanceId']  = instance_id

    return event

if __name__ == "__main__":
    import argparse, json
    parser = argparse.ArgumentParser()
    parser.add_argument("--exec", type=str, help="")
    args      = parser.parse_args()
    with open(args.exec,'r') as fp:
        exec = json.load(fp)
    lambda_handler(exec,"")