<template>
  <div class="cd-merge" :class="{ 'has-pr': Boolean(guide.pr_url) }">
    <div class="cd-merge-head">
      <span class="cd-merge-badge">合入指引</span>
      <span class="cd-merge-flag">未合入 {{ guide.base_branch || 'main' }}</span>
    </div>
    <p class="cd-merge-title">{{ guide.title || '写码完成 · 请自行合入 main' }}</p>
    <p class="cd-merge-summary">{{ guide.summary }}</p>

    <div class="cd-merge-meta">
      <div class="cd-merge-row">
        <span class="k">工作分支</span>
        <span class="v mono">{{ guide.work_branch }}</span>
      </div>
      <div class="cd-merge-row">
        <span class="k">合入目标</span>
        <span class="v mono">{{ guide.base_branch || 'main' }}</span>
      </div>
      <div v-if="guide.repo" class="cd-merge-row">
        <span class="k">仓库</span>
        <span class="v mono">{{ guide.repo }}</span>
      </div>
    </div>

    <div class="cd-merge-actions">
      <a
        v-if="guide.branch_url"
        class="cd-merge-link"
        :href="guide.branch_url"
        target="_blank"
        rel="noopener noreferrer"
      >查看工作分支</a>
      <a
        v-if="guide.compare_url"
        class="cd-merge-link primary"
        :href="guide.compare_url"
        target="_blank"
        rel="noopener noreferrer"
      >对比 {{ guide.base_branch || 'main' }}…{{ guide.work_branch }}</a>
      <a
        v-if="guide.pr_url"
        class="cd-merge-link primary"
        :href="guide.pr_url"
        target="_blank"
        rel="noopener noreferrer"
      >打开已创建的 PR</a>
      <a
        v-else-if="guide.new_pr_url"
        class="cd-merge-link"
        :href="guide.new_pr_url"
        target="_blank"
        rel="noopener noreferrer"
      >用网页开 PR</a>
    </div>
    <p class="cd-merge-note">
      同窗继续提需求会接着改工作分支。
      <strong>不要以为代码已经在 main 上，更不要以为本机 ERP 已经更新</strong>
      ——须合入目标分支后，在本机仓库 pull 并重启前后端，浏览器才能看到新界面。
    </p>
  </div>
</template>

<script setup>
defineProps({
  guide: {
    type: Object,
    required: true,
  },
})
</script>

<style scoped>
.cd-merge {
  align-self: stretch;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  margin: 10px 0 2px;
  padding: 14px 16px 12px;
  border: 1px solid #d7e0ea;
  border-radius: 12px;
  background: linear-gradient(180deg, #f7fafc 0%, #fff 55%);
  font-size: 12px;
  line-height: 1.5;
  color: #1f2630;
}

.cd-merge.has-pr {
  border-color: #c5ddce;
  background: linear-gradient(180deg, #f4faf6 0%, #fff 55%);
}

.cd-merge-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}

.cd-merge-badge {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #2f548c;
}

.cd-merge-flag {
  font-size: 11px;
  font-weight: 600;
  color: #9a3412;
  background: #fff7ed;
  border: 1px solid #fed7aa;
  border-radius: 999px;
  padding: 2px 8px;
}

.cd-merge-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #1f2630;
}

.cd-merge-summary {
  margin: 6px 0 0;
  font-size: 12px;
  color: #4a5568;
  line-height: 1.55;
}

.cd-merge-meta {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.cd-merge-row {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.9);
}

.cd-merge-row .k {
  color: #6b7c8f;
}

.cd-merge-row .v.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-weight: 500;
  color: #3a4250;
  word-break: break-all;
}

.cd-merge-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.cd-merge-link {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid #d0d7e0;
  background: #fff;
  color: #2f548c;
  text-decoration: none;
  font-size: 12px;
  font-weight: 600;
}

.cd-merge-link:hover {
  background: #f1f5f9;
  border-color: #94a3b8;
}

.cd-merge-link.primary {
  background: #2f548c;
  border-color: #2f548c;
  color: #fff;
}

.cd-merge-link.primary:hover {
  background: #254572;
}

.cd-merge-note {
  margin: 10px 0 0;
  font-size: 11px;
  color: #7a8494;
}
</style>
