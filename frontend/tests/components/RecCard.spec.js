import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import RecCard from '../../src/components/recommend/RecCard.vue'

vi.mock('../../src/utils/postThumbnail', () => ({
  createPostThumbnail: () => 'data:image/svg+xml;base64,stub',
}))

const RouterLinkStub = {
  props: ['to'],
  template: '<a :href="to"><slot /></a>',
}

function makeItem(overrides = {}) {
  return {
    post_id: 7,
    title: '推荐算法演进',
    summary: '从协同过滤到图神经网络。',
    author_name: '李四',
    domain_name: '算法',
    tags: ['CF', 'GNN'],
    view_count: 50,
    like_count: 5,
    created_at: '2026-04-10T00:00:00Z',
    graph_path_text: '你关注的人点赞过这篇',
    ...overrides,
  }
}

describe('RecCard', () => {
  it('渲染标题与图谱解释', () => {
    const wrapper = mount(RecCard, {
      props: { item: makeItem() },
      global: { stubs: { RouterLink: RouterLinkStub } },
    })
    expect(wrapper.find('.title').text()).toBe('推荐算法演进')
    expect(wrapper.find('.graph-path').text()).toContain('关注')
  })

  it('无 graph_path_text 时不渲染图谱解释', () => {
    const wrapper = mount(RecCard, {
      props: { item: makeItem({ graph_path_text: '' }) },
      global: { stubs: { RouterLink: RouterLinkStub } },
    })
    expect(wrapper.find('.graph-path').exists()).toBe(false)
  })

  it('点击“推荐理由”触发 showReason 事件', async () => {
    const wrapper = mount(RecCard, {
      props: { item: makeItem() },
      global: { stubs: { RouterLink: RouterLinkStub } },
    })
    const buttons = wrapper.findAll('.action-link')
    await buttons[0].trigger('click')
    expect(wrapper.emitted('showReason')).toBeTruthy()
    expect(wrapper.emitted('showReason')[0][0].post_id).toBe(7)
  })

  it('allowFeedback=true 时显示“不感兴趣”按钮', () => {
    const wrapper = mount(RecCard, {
      props: { item: makeItem(), allowFeedback: true },
      global: { stubs: { RouterLink: RouterLinkStub } },
    })
    expect(wrapper.find('.action-link--danger').exists()).toBe(true)
  })

  it('allowFeedback=false 时隐藏“不感兴趣”按钮', () => {
    const wrapper = mount(RecCard, {
      props: { item: makeItem(), allowFeedback: false },
      global: { stubs: { RouterLink: RouterLinkStub } },
    })
    expect(wrapper.find('.action-link--danger').exists()).toBe(false)
  })
})
