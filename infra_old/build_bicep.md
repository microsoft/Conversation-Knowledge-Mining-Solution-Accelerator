**Run below code to build bicep.json after changes**

az bicep build --file main.bicep

**Creates Resource group**
az group create --name <your-resource-group-name> --location <yourlocation>

**Deploys bicep template**
az deployment group create --resource-group <your-resource-group-name> --template-file master.bicep