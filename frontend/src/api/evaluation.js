import request from './index'

export function getEvaluationReports(dataset) {
  return request.get('/evaluation/reports', {
    params: dataset ? { dataset } : {},
  })
}
