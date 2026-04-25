import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import PostCard from '../../src/components/post/PostCard.vue'

const routerStub = { push: vi.fn() }

vi.mock('vue-router', () => ({
  useRouter: () => routerStub,
}))

vi.mock('../../src/utils/postThumbnail', () => ({
  createPostThumbnail: () => 'data:image/svg+xml;base64,stub',
}))

function makePost(overrides = {}) {
  return {
    id: 42,
    title: '如何理解推荐系统',
    summary: '讲解召回与精排的差异。',
    author_name: '张三',
    domain_name: '机器学习',
    tags: ['CF', 'Swing', 'GBDT'],
    view_count: 120,
    like_count: 8,
    created_at: '2026-04-01T00:00:00Z',
    ...overrides,
  }
}

describe('PostCard', () => {
  it('渲染标题与摘要', () => {
    const wrapper = mount(PostCard, { props: { post: makePost() } })
    expect(wrapper.find('.title').text()).toBe('如何理解推荐系统')
    expect(wrapper.find('.summary').text()).toContain('召回')
  })

  it('展示前三个标签', () => {
    const wrapper = mount(PostCard, { props: { post: makePost({ tags: ['a', 'b', 'c', 'd', 'e'] }) } })
    expect(wrapper.findAll('.topic-pill')).toHaveLength(3)
  })

  it('无摘要时使用占位文案', () => {
    const wrapper = mount(PostCard, { props: { post: makePost({ summary: '' }) } })
    expect(wrapper.find('.summary').text()).toMatch(/摘要/)
  })

  it('点击卡片跳转到详情页', async () => {
    routerStub.push.mockClear()
    const wrapper = mount(PostCard, { props: { post: makePost() } })
    await wrapper.trigger('click')
    expect(routerStub.push).toHaveBeenCalledWith('/posts/42')
  })

  it('展示浏览量与点赞数', () => {
    const wrapper = mount(PostCard, { props: { post: makePost() } })
    const metas = wrapper.findAll('.meta-item').map((n) => n.text())
    expect(metas.some((t) => t.includes('120'))).toBe(true)
    expect(metas.some((t) => t.includes('8'))).toBe(true)
  })
})
