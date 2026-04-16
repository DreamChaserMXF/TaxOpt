<template>
  <scroll-view scroll-y class="page">
    <view v-if="history.length > 0" class="card">
      <view class="page-head">
        <view>
          <text class="section-title">全部历史记录</text>
          <text class="page-sub">支持查看结果或回到首页继续编辑参数</text>
        </view>
        <text class="history-clear" @tap="clearHistory">清空全部</text>
      </view>

      <view v-for="entry in history" :key="entry.id" class="entry-card">
        <view class="entry-main" @tap="openResult(entry)">
          <text class="entry-label">{{ entry.label }}</text>
          <text class="entry-time">{{ entry.at }}</text>
        </view>
        <view class="entry-actions">
          <text class="entry-action primary" @tap="openResult(entry)">查看结果</text>
          <text class="entry-action" @tap="editEntry(entry)">重新编辑</text>
          <text class="entry-action danger" @tap="deleteHistory(entry.id)">删除</text>
        </view>
      </view>
    </view>

    <view v-else class="empty-card">
      <text class="empty-title">还没有历史记录</text>
      <text class="empty-sub">先回到首页完成一次计算，这里就会自动保存。</text>
      <button class="btn-back" @tap="goBack">返回首页</button>
    </view>
  </scroll-view>
</template>

<script>
import { ref } from '@vue/composition-api'
import { onShow } from '@dcloudio/uni-app'

export default {
  setup() {
    const HISTORY_KEY = 'taxopt_history'
    const RESULT_KEY = 'taxopt_result'
    const PREFILL_KEY = 'taxopt_prefill'

    const history = ref([])

    function refreshHistory() {
      history.value = uni.getStorageSync(HISTORY_KEY) || []
    }

    onShow(() => {
      refreshHistory()
    })

    function openResult(entry) {
      uni.setStorageSync(RESULT_KEY, entry.result)
      uni.navigateTo({ url: '/pages/result/result' })
    }

    function editEntry(entry) {
      uni.setStorageSync(PREFILL_KEY, entry.params)
      uni.showToast({ title: '已回填到首页', icon: 'none' })
      const pages = getCurrentPages()
      if (pages.length > 1) {
        uni.navigateBack()
      } else if (typeof uni.switchTab === 'function') {
        uni.switchTab({ url: '/pages/index/index' })
      } else {
        uni.reLaunch({ url: '/pages/index/index' })
      }
    }

    function deleteHistory(id) {
      const list = history.value.filter(entry => entry.id !== id)
      history.value = list
      uni.setStorageSync(HISTORY_KEY, list)
    }

    function clearHistory() {
      history.value = []
      uni.removeStorageSync(HISTORY_KEY)
      uni.showToast({ title: '历史记录已清空', icon: 'none' })
    }

    function goBack() {
      const pages = getCurrentPages()
      if (pages.length > 1) {
        uni.navigateBack()
      } else {
        uni.reLaunch({ url: '/pages/index/index' })
      }
    }

    return {
      history,
      openResult,
      editEntry,
      deleteHistory,
      clearHistory,
      goBack,
    }
  },
}
</script>

<style lang="scss" scoped>
.page {
  background: $bg-page;
  min-height: 100vh;
  padding: 24rpx;
  box-sizing: border-box;
}

.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16rpx;
  margin-bottom: 20rpx;
}

.page-sub {
  display: block;
  margin-top: 8rpx;
  font-size: 22rpx;
  color: $text-muted;
}

.entry-card {
  background: #f8fafc;
  border-radius: 16rpx;
  padding: 20rpx;
  margin-bottom: 16rpx;
}

.entry-main {
  margin-bottom: 14rpx;
}

.entry-label {
  display: block;
  font-size: 26rpx;
  color: $text-base;
  font-weight: 600;
  line-height: 1.5;
}

.entry-time {
  display: block;
  margin-top: 8rpx;
  font-size: 22rpx;
  color: $text-muted;
}

.entry-actions {
  display: flex;
  align-items: center;
  gap: 24rpx;
  flex-wrap: wrap;
}

.entry-action {
  font-size: 24rpx;
  color: #475569;
}

.entry-action.primary {
  color: $primary;
}

.entry-action.danger,
.history-clear {
  color: #ef4444;
}

.history-clear {
  font-size: 24rpx;
  white-space: nowrap;
}

.empty-card {
  background: #fff;
  border-radius: 20rpx;
  padding: 40rpx 32rpx;
  text-align: center;
}

.empty-title {
  display: block;
  font-size: 30rpx;
  color: $text-base;
  font-weight: 600;
  margin-bottom: 12rpx;
}

.empty-sub {
  display: block;
  font-size: 24rpx;
  color: $text-muted;
  line-height: 1.6;
  margin-bottom: 28rpx;
}

.btn-back {
  width: 100%;
  height: 88rpx;
  background: $primary;
  color: #fff;
  font-size: 28rpx;
  border-radius: 16rpx;
  border: none;
}
</style>
