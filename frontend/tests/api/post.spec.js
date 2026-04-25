import { describe, it, expect, vi, beforeEach } from 'vitest'

const { getMock, postMock, putMock, deleteMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
  postMock: vi.fn(),
  putMock: vi.fn(),
  deleteMock: vi.fn(),
}))

vi.mock('../../src/api/index', () => ({
  default: { get: getMock, post: postMock, put: putMock, delete: deleteMock },
}))

import {
  getPostList,
  getPostDetail,
  getHotPosts,
  recordBehavior,
  deletePost,
} from '../../src/api/post'

beforeEach(() => {
  getMock.mockReset().mockResolvedValue({ data: {} })
  postMock.mockReset().mockResolvedValue({ data: {} })
  putMock.mockReset().mockResolvedValue({ data: {} })
  deleteMock.mockReset().mockResolvedValue({ data: {} })
})

describe('post API client', () => {
  it('getPostList 传入默认分页', () => {
    getPostList()
    expect(getMock).toHaveBeenCalledWith('/post/list', {
      params: { page: 1, per_page: 20 },
    })
  })

  it('getPostList 带 domainId 时加入 params', () => {
    getPostList(2, 10, 5)
    expect(getMock).toHaveBeenCalledWith('/post/list', {
      params: { page: 2, per_page: 10, domain_id: 5 },
    })
  })

  it('getPostDetail 使用 post id 拼接路径', () => {
    getPostDetail(42)
    expect(getMock).toHaveBeenCalledWith('/post/42')
  })

  it('getHotPosts 传入 limit', () => {
    getHotPosts(5)
    expect(getMock).toHaveBeenCalledWith('/post/hot', { params: { limit: 5 } })
  })

  it('recordBehavior POST 行为类型', () => {
    recordBehavior(10, 'like')
    expect(postMock).toHaveBeenCalledWith('/post/10/behavior', { behavior_type: 'like' })
  })

  it('recordBehavior 合并 extra 字段', () => {
    recordBehavior(10, 'browse', { duration: 30 })
    expect(postMock).toHaveBeenCalledWith('/post/10/behavior', {
      behavior_type: 'browse',
      duration: 30,
    })
  })

  it('deletePost 调用 DELETE', () => {
    deletePost(99)
    expect(deleteMock).toHaveBeenCalledWith('/post/99')
  })
})
