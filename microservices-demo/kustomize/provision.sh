# run this script from the "kustomize" directory of the Boutique microservices-demo tree!
# be sure to set the components config in kustomize before running the first time

# arg 1 is the name of the cluster as given on the gcloud create command
cluster=$1

# install istioctl with enough capacity to run demos
istioctl install --set profile=demo -y

ret=`kubectl get deploy -n istio-system | grep istiod`
if [ -z "$ret" ]
then
      echo "istio install failed, please retry...exiting"
      exit 1
else
      echo "istio install complete"
fi

# mark the default namespace to set up istio side-car injection when app is deployed
kubectl label namespace default istio-injection=enabled --overwrite=true

# fetch the "all" firewall rule name so it can be updated with ports to open
cluster_info=`gcloud compute firewall-rules list --filter="name~gke-${cluster}-[0-9a-z-]*-all" --format=json`

# get just the raw text name for the "all" rule using jq
cluster_name=`echo $cluster_info | jq -r '.[0].name'`

echo $cluster_name

# update the firewall "all" rule to open needed ports
gcloud compute firewall-rules update $cluster_name --allow tcp:10250,tcp:443,tcp:15017

# install the app using kustomize (be sure to have set the config first time running this)
kubectl apply -k .

# check the service to be sure the external ip is being provisioned...may need to do this a couple of times afterwards
kubectl get svc
