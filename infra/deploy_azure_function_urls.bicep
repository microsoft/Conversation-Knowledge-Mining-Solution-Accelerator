@description('Specifies the location for resources.')
param solutionName string 
// param identity string

var chartsfunctionAppName = '${solutionName}-charts-fn'
var chartsfunctionName = 'get_metrics'
resource existingFunctionApp 'Microsoft.Web/sites@2021-02-01' existing = {
  name: chartsfunctionAppName
}
var charts_function_url = 'https://${existingFunctionApp.properties.defaultHostName}/api/${chartsfunctionName}?data_type=charts'
var filters_function_url = 'https://${existingFunctionApp.properties.defaultHostName}/api/${chartsfunctionName}?data_type=filters'

var ragfunctionAppName = '${solutionName}-rag-fn'
var ragfunctionName = 'stream_openai_text'
resource existingragFunctionApp 'Microsoft.Web/sites@2021-02-01' existing = {
  name: ragfunctionAppName
}
var rag_function_url = 'https://${existingragFunctionApp.properties.defaultHostName}/api/${ragfunctionName}'


// var graphragfunctionAppName = '${solutionName}-rag-fn'
// var graphragfunctionName = 'get_metrics'
// resource existinggraphragFunctionApp 'Microsoft.Web/sites@2021-02-01' existing = {
//   name: graphragfunctionAppName
// }
// var graphrag_function_url = 'https://${existinggraphragFunctionApp.properties.defaultHostName}/api/${graphragfunctionName}'

var graphrag_function_url = 'TBD'

output functionURLsOutput object = {
  charts_function_url:charts_function_url
  filters_function_url:filters_function_url
  rag_function_url:rag_function_url
  graphrag_function_url:graphrag_function_url
}
