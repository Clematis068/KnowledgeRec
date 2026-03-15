import request from './index'

export function getEvaluationReports() {
  return request.get('/evaluation/reports')
}
