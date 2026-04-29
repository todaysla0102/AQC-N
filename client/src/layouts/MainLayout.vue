<template>
  <div
    class="aqc-shell"
    :class="{ collapsed: sidebarCollapsed && !isMobile }"
    :style="isMobile ? undefined : { '--sidebar-width': sidebarCollapsed ? '88px' : '292px' }"
  >
    <aside
      class="aqc-sidebar shell-stage shell-sidebar"
      :class="{
        collapsed: sidebarCollapsed && !isMobile,
        mobile: isMobile,
        open: mobileOpen,
        'copy-visible': sidebarTextVisible || isMobile,
        'footer-visible': sidebarFooterTextVisible || isMobile,
        'menu-intro-visible': sidebarIntroVisible,
      }"
      @transitionend="handleSidebarTransitionEnd"
    >
        <div class="brand-box">
          <div class="brand-mark">
          <img :key="`aqc-logo-${themeLogoKey}`" src="/aqc-logo.svg" alt="AQC Logo" class="theme-sensitive-logo" :style="themeSensitiveLogoStyle" />
          </div>
        </div>

      <div ref="menuScrollRef" class="menu-scroll">
        <nav class="menu-list">
          <RouterLink
            v-for="(item, index) in visibleMenus"
            :key="item.key"
            :to="item.to"
            class="menu-item"
            :class="{ active: isActive(item) }"
            :style="{ '--menu-seq': index + 1 }"
            @click="handleMenuClick"
          >
            <el-icon class="menu-icon">
              <component :is="item.icon" />
            </el-icon>
            <div class="menu-copy">
              <span class="sidebar-copy-block">{{ item.label }}</span>
            </div>
          </RouterLink>
        </nav>
      </div>

      <div class="sidebar-bottom">
        <div class="sidebar-controls">
          <button type="button" class="collapse-trigger" @click="toggleSidebar">
            <el-icon>
              <component :is="sidebarCollapsed ? Expand : Fold" />
            </el-icon>
            <span class="sidebar-copy-inline">收缩侧栏</span>
          </button>
        </div>

        <footer class="sidebar-footer">
          <div class="sidebar-footer-content">
            <div v-if="sidebarCollapsed && !isMobile" class="sidebar-footer-mark">
              <img :key="`symuse-logo-${themeLogoKey}`" src="/symuse-icon.svg" alt="SyMuse" class="theme-sensitive-logo" :style="themeSensitiveLogoStyle" />
            </div>
            <div class="sidebar-footer-copy">
              <a href="https://symuse.com" target="_blank" rel="noopener noreferrer">
                © 2013 - 2026 SyMuse Inc. 保留所有权利。
              </a>
            </div>

            <div class="sidebar-footer-icp">
              <a href="https://beian.miit.gov.cn/" target="_blank" rel="noopener noreferrer">
                ICP备案号： 鄂ICP备2021005393号-1
              </a>
            </div>
          </div>
        </footer>
      </div>
    </aside>

    <div v-if="isMobile && mobileOpen" class="mobile-mask" @click="mobileOpen = false" />

    <section class="aqc-main">
      <header class="aqc-header shell-stage shell-header" :class="{ 'card-surface': !isMobile, 'mobile-no-card': isMobile }">
        <div class="header-left">
          <el-button v-if="isMobile" circle class="head-icon-btn" @click="toggleSidebar">
            <el-icon><component :is="mobileOpen ? Fold : Expand" /></el-icon>
          </el-button>

          <div class="header-title">
            <h2>{{ headerTitle }}</h2>
            <p v-if="!isMobile">{{ headerSubtitle }}</p>
          </div>
        </div>

        <div class="header-right">
          <Dw5000Clock v-if="!isMobile" />
          <button
            v-if="appVersionStore.hasUpdate"
            type="button"
            class="header-upgrade-chip"
            @click="upgradeToLatestVersion"
          >
            <el-icon><RefreshRight /></el-icon>
            <span>进入新版本</span>
          </button>
          <el-button circle class="head-icon-btn" aria-label="全局搜索" @click.stop="openGlobalSearch">
            <el-icon><Search /></el-icon>
          </el-button>
          <div
            ref="settingsAnchorRef"
            class="header-settings"
          >
            <el-button
              circle
              class="head-icon-btn head-settings-btn"
              aria-label="设置与通知"
              @click.stop="toggleSettingsMenu"
            >
              <span v-if="notificationBadgeVisible" class="header-notification-dot" aria-hidden="true"></span>
              <el-icon><Setting /></el-icon>
            </el-button>
          </div>
        </div>
      </header>

      <main ref="contentRef" class="aqc-content shell-stage shell-content">
        <RouterView v-slot="{ Component, route: currentRoute }">
          <div :key="currentRoute.path" class="page-transition-shell">
            <component :is="Component" />
          </div>
        </RouterView>
      </main>
    </section>

    <Teleport to="body">
      <transition name="settings-float">
        <div
          v-if="settingsMenuVisible"
          class="header-floating-menu-layer"
        >
          <div
            class="header-floating-menu-backdrop"
            @click="closeSettingsMenu"
          ></div>
          <div
            ref="settingsMenuPortalRef"
            class="header-floating-menu-portal"
            :style="settingsMenuStyle"
            @click.stop
          >
            <div class="header-floating-menu card-surface">
            <div class="header-floating-menu-section">
              <span class="header-floating-menu-label">面板切换</span>
              <div class="header-panel-toggle" role="tablist" aria-label="设置与通知切换">
                <button
                  type="button"
                  class="header-panel-toggle-btn"
                  :class="{ active: headerPanelSection === 'settings' }"
                  @click.stop.prevent="openSettingsSection"
                >
                  设置
                </button>
                <button
                  type="button"
                  class="header-panel-toggle-btn"
                  :class="{ active: headerPanelSection === 'notifications' }"
                  @click.stop.prevent="openNotificationSection"
                >
                  通知
                </button>
              </div>
            </div>

            <div v-if="headerPanelSection === 'settings'" class="header-floating-menu-section">
              <span class="header-floating-menu-label">主题模式</span>
              <div class="header-theme-options">
                <button
                  v-for="item in themeOptions"
                  :key="item.value"
                  type="button"
                  class="header-theme-option"
                  :class="{ active: themeStore.mode === item.value }"
                  @click="setThemeMode(item.value)"
                >
                  <el-icon>
                    <component :is="item.icon" />
                  </el-icon>
                  <span>{{ item.label }}</span>
                </button>
              </div>
            </div>

            <template v-if="headerPanelSection === 'settings'">
              <div v-if="!isMobile" class="header-floating-menu-section">
                <span class="header-floating-menu-label">侧边栏默认</span>
                <div class="header-setting-switch-row">
                  <span>默认伸展</span>
                  <el-switch
                    :model-value="sidebarDefaultExpanded"
                    @change="setSidebarDefaultExpanded"
                  />
                </div>
              </div>

              <div class="header-floating-menu-section">
                <span class="header-floating-menu-label">系统版本</span>
                <div
                  class="header-version-card"
                  :class="{ stale: appVersionStore.hasUpdate }"
                  role="button"
                  tabindex="0"
                  @click="openUpdateLogDialog"
                  @keydown.enter.prevent="openUpdateLogDialog"
                  @keydown.space.prevent="openUpdateLogDialog"
                >
                  <div class="header-version-card-head">
                    <strong>{{ appVersionStore.currentVersionLabel }}</strong>
                  </div>
                  <p v-if="appVersionStore.hasUpdate">
                    当前处于旧版本，最新版本为 {{ appVersionStore.latestVersionLabel }}
                  </p>
                  <p v-else>当前已是最新版本</p>
                  <div class="header-version-card-actions">
                    <el-button
                      v-if="appVersionStore.hasUpdate"
                      size="small"
                      type="primary"
                      @click.stop="upgradeToLatestVersion"
                    >
                      进入新版本
                    </el-button>
                  </div>
                  <span class="header-version-card-link">查看更新日志</span>
                </div>
              </div>

              <div class="header-floating-menu-actions">
                <button v-if="isMobile" type="button" class="header-floating-action" @click="openSymuseQrLoginDialog">
                  <el-icon><Camera /></el-icon>
                  <span>扫码登录</span>
                </button>
                <button type="button" class="header-floating-action danger" @click="onLogout">
                  <el-icon><SwitchButton /></el-icon>
                  <span>{{ `退出账号 ${authStore.displayName || '当前账号'}` }}</span>
                </button>
              </div>
            </template>
            <div v-else class="header-floating-menu-section">
              <div class="header-floating-menu-head">
                <span class="header-floating-menu-label">通知中心</span>
                <span v-if="notificationsUnreadCount" class="header-floating-menu-tag">{{ notificationsUnreadCount }} 条待处理</span>
              </div>

              <div class="header-notification-card">
                <div v-if="notifications.length" class="header-notification-list">
                  <article
                    v-for="item in notifications"
                    :key="item.id"
                    class="header-notification-item"
                  >
                    <div class="header-notification-copy">
                      <div class="header-notification-meta">
                        <span class="header-notification-chip">{{ formatNotificationTypeLabel(item) }}</span>
                        <span class="header-notification-time">{{ formatNotificationTime(item.createdAt) }}</span>
                      </div>
                      <strong>{{ item.title }}</strong>
                      <p v-if="buildNotificationDetail(item)">{{ buildNotificationDetail(item) }}</p>
                    </div>
                    <div class="header-notification-actions">
                      <template v-if="item.notificationType === 'report_delivery'">
                        <el-button size="small" @click="dismissNotification(item)">关闭</el-button>
                        <el-button size="small" type="primary" @click="openReportNotification(item)">查看报告</el-button>
                      </template>
                      <template v-else>
                        <el-button size="small" @click="respondNotification(item, false)">拒绝</el-button>
                        <el-button size="small" type="primary" @click="respondNotification(item, true)">加入</el-button>
                      </template>
                    </div>
                  </article>
                </div>
                <div v-else class="header-account-card header-account-card-muted">
                  <strong>{{ notificationLoading ? '通知加载中' : '暂无待处理通知' }}</strong>
                </div>

                <div class="header-notification-foot">
                  <el-button
                    v-if="notificationSupported && notificationPermission !== 'granted'"
                    size="small"
                    @click="requestBrowserNotifications"
                  >
                    {{ notificationRequesting ? '开启中...' : '开启浏览器通知' }}
                  </el-button>
                  <span v-else-if="notificationSupported && notificationPermission === 'granted'" class="header-notification-status">浏览器通知已开启</span>
                </div>
              </div>
            </div>
            </div>
          </div>
        </div>
      </transition>
    </Teleport>

    <ResponsiveDialog
      v-model="updateLogVisible"
      title="更新日志"
      width="min(760px, 94vw)"
      class="aqc-app-dialog update-log-dialog"
      mobile-subtitle="页眉设置"
      :initial-snap="0.62"
      :expanded-snap="0.94"
    >
      <div class="update-log-shell">
        <section class="update-log-summary">
          <div class="update-log-summary-copy">
            <span>当前版本</span>
            <strong>{{ appVersionStore.currentVersionLabel }}</strong>
            <p v-if="appVersionStore.hasUpdate">检测到新版本 {{ appVersionStore.latestVersionLabel }}，可以先查看变更再升级。</p>
            <p v-else>这里会汇总近期版本更新内容。每次发版都会同步维护开发日志与更新日志。</p>
          </div>
          <div class="update-log-summary-actions">
            <el-button :loading="updateLogLoading" @click="refreshUpdateLog">刷新日志</el-button>
            <el-button v-if="appVersionStore.hasUpdate" type="primary" @click="upgradeToLatestVersion">进入新版本</el-button>
          </div>
        </section>

        <div v-if="updateLogLoading && !updateLogEntries.length" class="update-log-empty">
          <strong>更新日志加载中</strong>
          <p>正在读取最近的版本变更记录。</p>
        </div>

        <div v-else-if="updateLogError && !updateLogEntries.length" class="update-log-empty">
          <strong>更新日志暂时不可用</strong>
          <p>{{ updateLogError }}</p>
        </div>

        <div v-else class="update-log-list">
          <article
            v-for="entry in updateLogEntries"
            :key="`${entry.date}-${entry.version || ''}-${entry.title}`"
            class="update-log-entry"
          >
            <div class="update-log-entry-head">
              <div class="update-log-entry-copy">
                <div class="update-log-entry-meta">
                  <span>{{ entry.date }}</span>
                  <span v-if="entry.version" class="update-log-entry-tag">{{ entry.version }}</span>
                  <span v-if="entry.scope" class="update-log-entry-tag">{{ entry.scope }}</span>
                </div>
                <strong>{{ entry.title }}</strong>
                <p v-if="entry.summary">{{ entry.summary }}</p>
              </div>
            </div>
            <ul v-if="entry.highlights.length" class="update-log-entry-list">
              <li v-for="item in entry.highlights" :key="item">{{ item }}</li>
            </ul>
          </article>
        </div>

        <div class="update-log-history-action">
          <el-button class="dashboard-secondary-action" @click="openUpdateLogHistory">查看历史版本日志</el-button>
        </div>
      </div>
    </ResponsiveDialog>

    <ResponsiveDialog
      v-model="symuseQrLoginVisible"
      title="扫码登录"
      width="min(520px, 94vw)"
      class="aqc-app-dialog header-qr-login-dialog"
      mobile-subtitle="页眉设置"
      :initial-snap="0.62"
      :expanded-snap="0.94"
    >
      <div class="header-qr-login-shell">
        <section v-if="symuseQrFlowState === 'scanner'" class="header-qr-login-camera">
          <div class="header-qr-login-camera-frame" @click="focusSymuseQrScannerAt" @touchstart.passive="focusSymuseQrScannerAt">
            <video
              ref="symuseQrVideoRef"
              class="header-qr-login-video"
              autoplay
              muted
              playsinline
            />
            <div class="header-qr-login-reticle" aria-hidden="true"></div>
          </div>
          <div class="header-qr-login-camera-copy">
            <strong>{{ symuseQrPanelTitle }}</strong>
            <p>{{ symuseQrPanelDetail }}</p>
          </div>
        </section>

        <section v-else class="header-qr-login-confirm-panel">
          <div class="header-qr-login-confirm-copy">
            <span class="header-qr-login-chip">{{ symuseQrStatusLabel }}</span>
            <strong>{{ symuseQrPanelTitle }}</strong>
            <p>{{ symuseQrPanelDetail }}</p>
          </div>

          <label class="header-qr-login-checkbox">
            <input v-model="symuseQrLoginOnceOnly" type="checkbox" />
            <span>仅登录一次</span>
          </label>
          <p class="header-qr-login-checkbox-hint">默认仅登录一次。勾选后桌面端不会记住密码，也不会自动登录。</p>

          <div class="header-qr-login-actions">
            <el-button :disabled="symuseQrConfirming || symuseQrCancelling" @click="cancelSymuseQrLoginRequest">
              取消
            </el-button>
            <el-button type="primary" :loading="symuseQrConfirming" :disabled="symuseQrCancelling" @click="confirmSymuseQrLoginRequest">
              确认登录
            </el-button>
          </div>
        </section>
      </div>
    </ResponsiveDialog>

    <el-dialog
      v-model="searchVisible"
      width="min(720px, 92vw)"
      append-to-body
      align-center
      destroy-on-close
      :z-index="GLOBAL_SEARCH_Z_INDEX"
      :modal="false"
      :show-close="false"
      class="aqc-app-dialog global-search-dialog"
      @open="focusGlobalSearchInput"
      @opened="focusGlobalSearchInput"
    >
      <div class="global-search-shell" :class="{ expanded: searchBodyVisible }">
        <div class="global-search-input-shell">
          <el-icon class="global-search-input-icon"><Search /></el-icon>
          <input
            ref="searchInputRef"
            v-model.trim="searchKeyword"
            type="text"
            class="global-search-input"
            placeholder="搜索商品、订单、工单、店铺、库存分布"
            inputmode="search"
            enterkeyhint="search"
            autocomplete="off"
            autocapitalize="off"
            spellcheck="false"
            @keydown.down.prevent="moveSearchSelection(1)"
            @keydown.up.prevent="moveSearchSelection(-1)"
            @keydown.enter.prevent="handleGlobalSearchEnter"
            @keydown.esc.prevent="searchVisible = false"
          />
          <button
            v-if="searchKeyword"
            type="button"
            class="global-search-clear"
            aria-label="清空搜索"
            @click="searchKeyword = ''"
          >
            <el-icon><Close /></el-icon>
          </button>
        </div>

        <div
          class="global-search-body-shell"
          :class="{ expanded: searchBodyVisible }"
          :style="searchBodyStyle"
        >
          <Transition
            name="global-search-swap"
            mode="out-in"
            @after-enter="refreshSearchBodyHeight"
          >
            <div
              v-if="searchBodyVisible"
              :key="`search-${searchResultVersion}`"
              ref="searchBodyContentRef"
              class="global-search-body-content"
            >
              <div v-if="!searchResultGroups.length" class="global-search-empty">
                <strong>没有找到匹配结果</strong>
                <p>可以尝试更短的关键字，或切换到具体模块继续筛选。</p>
              </div>

              <div v-else class="global-search-results">
                <section
                  v-for="group in searchResultGroups"
                  :key="group.key"
                  class="global-search-group"
                >
                  <div class="global-search-group-head">
                    <el-icon><component :is="group.icon" /></el-icon>
                    <strong>{{ group.label }}</strong>
                    <span>{{ group.items.length }} 条</span>
                  </div>

                  <button
                    v-for="item in group.items"
                    :key="item.key"
                    type="button"
                    class="global-search-item"
                    :class="{ active: activeSearchKey === item.key }"
                    @mouseenter="activeSearchKey = item.key"
                    @click="openSearchResult(item)"
                  >
                    <div class="global-search-item-main">
                      <strong>{{ item.title }}</strong>
                      <span v-if="item.badge">{{ item.badge }}</span>
                    </div>
                    <p>{{ item.subtitle }}</p>
                  </button>
                </section>
              </div>
            </div>
          </Transition>
        </div>
      </div>
    </el-dialog>

    <ResponsiveDialog
      v-model="searchDistributionVisible"
      title="商品分布"
      mobile-subtitle="全局搜索"
      width="min(1120px, 96vw)"
      class="aqc-app-dialog goods-distribution-dialog global-search-distribution-dialog"
      :z-index="GLOBAL_SEARCH_Z_INDEX + 20"
      :mobile-base-z-index="GLOBAL_SEARCH_Z_INDEX + 20"
    >
      <div class="goods-distribution-shell" v-loading="searchDistributionLoading">
        <template v-if="isMobileViewport">
          <div class="goods-distribution-mobile-panel">
            <section class="goods-distribution-mobile-summary-bar">
              <article class="goods-distribution-mobile-summary-item">
                <span>总库存</span>
                <strong>{{ searchDistributionTotalStock }}</strong>
              </article>
              <article class="goods-distribution-mobile-summary-item">
                <span>库存金额</span>
                <strong>¥ {{ formatMoney(searchDistributionTotalAmount) }}</strong>
              </article>
            </section>

            <section class="goods-distribution-mobile-title">
              <strong>{{ searchDistributionTitle || '当前商品' }}</strong>
              <p>{{ searchDistributionSubtitle || '库存分布' }}</p>
            </section>

            <div class="goods-distribution-mobile-utility">
              <el-button @click="openGlobalSearchDistributionInventoryLog">库存日志</el-button>
            </div>

            <section class="goods-distribution-mobile-summary-bar">
              <article class="goods-distribution-mobile-summary-item">
                <span>有货点位</span>
                <strong>{{ searchDistributionPositiveCount }}</strong>
              </article>
              <article class="goods-distribution-mobile-summary-item">
                <span>点位明细</span>
                <strong>{{ searchDistributionRows.length }}</strong>
              </article>
            </section>
          </div>

          <section v-if="searchDistributionRows.length" class="goods-distribution-mobile-list">
            <article
              v-for="row in searchDistributionRows"
              :key="row.shopId"
              class="goods-distribution-mobile-row goods-distribution-row-actionable"
              role="button"
              tabindex="0"
              @click="openSearchDistributionActionMenu(row)"
              @keyup.enter="openSearchDistributionActionMenu(row)"
            >
              <div class="goods-distribution-mobile-main">
                <strong>{{ displayShopName(row.shopName || row.shopShortName) || '-' }}</strong>
                <span>{{ formatSearchDistributionShopType(row.shopType) }}<template v-if="row.unitPrice"> · 单价 ¥ {{ formatMoney(row.unitPrice) }}</template></span>
              </div>
              <div class="goods-distribution-mobile-side">
                <small>库存数量</small>
                <strong>{{ row.quantity }}</strong>
                <span>¥ {{ formatMoney(row.lineAmount) }}</span>
              </div>
            </article>
          </section>

          <div v-else class="goods-distribution-mobile-empty">
            <strong>暂无库存分布</strong>
            <p>当前商品还没有可展示的店铺或仓库库存。</p>
          </div>
        </template>

        <template v-else>
          <section class="inventory-hero-card inventory-hero-card-strong">
            <span>总库存</span>
            <strong>{{ searchDistributionTotalStock }}</strong>
            <h3>{{ searchDistributionTitle || '当前商品' }}</h3>
            <p>{{ searchDistributionSubtitle || '库存分布' }}</p>
            <div class="toolbar-actions inventory-hero-actions">
              <el-button @click="openGlobalSearchDistributionInventoryLog">库存日志</el-button>
            </div>
          </section>

          <div class="table-shell open-table-shell inventory-table-shell">
            <el-table
              :data="searchDistributionRows"
              border
              stripe
              empty-text="暂无库存分布"
              show-summary
              :summary-method="searchDistributionTableSummary"
              @row-click="openSearchDistributionActionMenu"
            >
              <el-table-column label="店铺 / 仓库名称" min-width="260" show-overflow-tooltip>
                <template #default="{ row }">{{ displayShopName(row.shopName || row.shopShortName) || '-' }}</template>
              </el-table-column>
              <el-table-column prop="quantity" label="库存数量" min-width="110" />
              <el-table-column prop="unitPrice" label="单价" min-width="120">
                <template #default="{ row }">¥ {{ formatMoney(row.unitPrice) }}</template>
              </el-table-column>
              <el-table-column prop="lineAmount" label="金额" min-width="140">
                <template #default="{ row }">¥ {{ formatMoney(row.lineAmount) }}</template>
              </el-table-column>
              <el-table-column label="点位类型" min-width="120">
                <template #default="{ row }">{{ formatSearchDistributionShopType(row.shopType) }}</template>
              </el-table-column>
            </el-table>
          </div>
        </template>
      </div>

      <template #footer>
        <div class="form-actions">
          <el-button @click="searchDistributionVisible = false">关闭</el-button>
        </div>
      </template>
    </ResponsiveDialog>

    <ResponsiveDialog
      v-model="searchDistributionActionMenuVisible"
      :title="searchDistributionActionTitle"
      width="min(360px, 92vw)"
      :z-index="GLOBAL_SEARCH_Z_INDEX + 30"
      :mobile-base-z-index="GLOBAL_SEARCH_Z_INDEX + 30"
      class="aqc-app-dialog goods-distribution-action-dialog"
      mobile-subtitle="全局搜索"
    >
      <section class="work-order-category-chooser goods-distribution-action-chooser">
        <button type="button" class="work-order-category-card goods-distribution-action-card" @click="createTransferFromSearchDistribution">
          <strong>创建商品调拨单</strong>
          <small>{{ searchDistributionActionSubtitle }}</small>
        </button>
        <button type="button" class="work-order-category-card goods-distribution-action-card" @click="viewSearchDistributionInventoryLogs">
          <strong>库存日志</strong>
          <small>{{ searchDistributionActionSubtitle }}</small>
        </button>
      </section>
    </ResponsiveDialog>
  </div>
</template>

<script setup>
import {
  Box,
  Camera,
  Close,
  Expand,
  Fold,
  Monitor,
  Moon,
  OfficeBuilding,
  RefreshRight,
  Search,
  Sell,
  Setting,
  ShoppingCart,
  Sunny,
  SwitchButton,
  Tickets,
} from '@element-plus/icons-vue'
import { BarcodeFormat } from '@zxing/library'
import { ElMessage } from 'element-plus'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'

import Dw5000Clock from '../components/DW5000Clock.vue'
import ResponsiveDialog from '../components/ResponsiveDialog.vue'
import { useMobileViewport } from '../composables/useMobileViewport'
import { useBarcodeScanner } from '../composables/useBarcodeScanner'
import { sidebarMenus } from '../data/modules'
import { apiGet, apiPost } from '../services/api'
import { useAppVersionStore } from '../stores/appVersion'
import { useAuthStore } from '../stores/auth'
import { useThemeStore } from '../stores/theme'
import {
  buildSymuseLogoutReturnTo,
  clearStoredLoginState,
  clearStoredPostLoginPath,
} from '../utils/authRedirect'
import { confirmAction } from '../utils/confirm'
import { buildLogCenterQuery, LOG_CENTER_TYPE_META, normalizeLogCenterType } from '../utils/logCenter'
import { displayShopName, normalizeLocationRow, SHOP_TYPE_OTHER_WAREHOUSE, SHOP_TYPE_REPAIR, SHOP_TYPE_WAREHOUSE } from '../utils/shops'
import { formatShanghaiDate, getShanghaiMinutes } from '../utils/shanghaiTime'
import { fetchUpdateLogEntries, UPDATE_LOG_FALLBACK_MESSAGE } from '../utils/updateLog'

const authStore = useAuthStore()
const appVersionStore = useAppVersionStore()
const themeStore = useThemeStore()
const { isMobileViewport } = useMobileViewport()
const route = useRoute()
const router = useRouter()

const SIDEBAR_DEFAULT_EXPANDED_KEY = 'aqc_n_sidebar_default_expanded'
const SETTINGS_MENU_OFFSET = 2

function resolveStoredSidebarDefaultExpanded() {
  if (typeof window === 'undefined') {
    return false
  }
  try {
    return String(window.localStorage.getItem(SIDEBAR_DEFAULT_EXPANDED_KEY) || '').trim() === '1'
  } catch (error) {
    console.warn('Failed to read sidebar default preference', error)
    return false
  }
}

function persistSidebarDefaultExpanded(value) {
  if (typeof window === 'undefined') {
    return
  }
  try {
    window.localStorage.setItem(SIDEBAR_DEFAULT_EXPANDED_KEY, value ? '1' : '0')
  } catch (error) {
    console.warn('Failed to persist sidebar default preference', error)
  }
}

const sidebarDefaultExpanded = ref(resolveStoredSidebarDefaultExpanded())
const sidebarCollapsed = ref(!sidebarDefaultExpanded.value)
const isMobile = ref(false)
const mobileOpen = ref(false)
const sidebarTextVisible = ref(false)
const sidebarIntroVisible = ref(false)
const sidebarFooterTextVisible = ref(false)
const greetingTick = ref(Date.now())
const contentRef = ref(null)
const menuScrollRef = ref(null)
const settingsAnchorRef = ref(null)
const settingsMenuPortalRef = ref(null)
const searchInputRef = ref(null)
const searchBodyContentRef = ref(null)
const settingsMenuVisible = ref(false)
const settingsMenuStyle = ref({})
const headerPanelSection = ref('settings')
const searchVisible = ref(false)
const updateLogVisible = ref(false)
const symuseQrLoginVisible = ref(false)
const updateLogLoading = ref(false)
const updateLogLoaded = ref(false)
const updateLogError = ref('')
const updateLogEntries = ref([])
const notificationSupported = ref(false)
const notificationPermission = ref('default')
const notificationRequesting = ref(false)
const notifications = ref([])
const notificationsUnreadCount = ref(0)
const notificationLoading = ref(false)
const searchKeyword = ref('')
const searchLoading = ref(false)
const searchResolved = ref(false)
const searchBodyHeight = ref(0)
const searchResultVersion = ref(0)
const searchResultGroups = ref([])
const activeSearchKey = ref('')
const searchDistributionVisible = ref(false)
const searchDistributionLoading = ref(false)
const searchDistributionItem = ref(null)
const searchDistributionInventories = ref([])
const searchDistributionTotalStock = ref(0)
const searchDistributionActionMenuVisible = ref(false)
const searchDistributionActionRow = ref(null)
const preserveSearchDistributionOnClose = ref(false)
const symuseQrFlowState = ref('scanner')
const symuseQrSessionToken = ref('')
const symuseQrStatus = ref('idle')
const symuseQrLastServiceLabel = ref('')
const symuseQrLastDeviceLabel = ref('')
const symuseQrScannedAt = ref('')
const symuseQrLoginOnceOnly = ref(true)
const symuseQrScanLoading = ref(false)
const symuseQrConfirming = ref(false)
const symuseQrCancelling = ref(false)
let greetingTimer = null
let sidebarTextTimer = null
let sidebarIntroTimer = null
let chartResizeTimers = []
let searchDebounceTimer = null
let searchAbortController = null
let notificationRefreshTimer = null
let searchFocusRetryTimers = []
let lastBrowserUnreadCount = 0

const SEARCH_LIMIT = 5
const GLOBAL_SEARCH_Z_INDEX = 96000
const themeOptions = [
  { value: 'light', label: '浅色', icon: Sunny },
  { value: 'dark', label: '深色', icon: Moon },
  { value: 'system', label: '跟随系统', icon: Monitor },
]
const searchTypeIcons = {
  goods: Box,
  distribution: Box,
  sales: Sell,
  orders: ShoppingCart,
  workOrders: Tickets,
  shops: OfficeBuilding,
}
const NOTIFICATION_TYPE_LABELS = {
  report_delivery: '报告通知',
  group_invite: '群组邀请',
}
const matchedMenu = computed(() => {
  return sidebarMenus.find((item) => isActive(item)) || null
})
const isEngineerRole = computed(() => authStore.aqcRoleKey === 'aqc_engineer')

async function loadUpdateLog({ force = false } = {}) {
  if (import.meta.env.DEV) {
    updateLogLoaded.value = false
  }
  if (updateLogLoading.value || (updateLogLoaded.value && !force)) {
    return
  }
  updateLogLoading.value = true
  updateLogError.value = ''
  try {
    const payload = await fetchUpdateLogEntries({ limit: 3 })
    updateLogEntries.value = payload.entries
    updateLogLoaded.value = true
  } catch (error) {
    console.error('Update log load failed', error)
    updateLogError.value = error instanceof Error && error.message ? error.message : UPDATE_LOG_FALLBACK_MESSAGE
  } finally {
    updateLogLoading.value = false
  }
}

function canViewMenu(item) {
  if (!item?.permission) {
    return true
  }
  try {
    return authStore.can(item.permission)
  } catch (error) {
    console.error('Failed to resolve sidebar permission', item.key, error)
    return authStore.isAdmin
  }
}

const visibleMenus = computed(() => {
  const mapMenuTarget = (item) => {
    if (isEngineerRole.value && item.key === 'sales-entry') {
      return { ...item, to: { name: 'repair-sales-entry' } }
    }
    if (isEngineerRole.value && item.key === 'sales-records') {
      return { ...item, to: { name: 'repair-sales-records' } }
    }
    return item
  }
  const allowedMenus = sidebarMenus.filter((item) => canViewMenu(item)).map(mapMenuTarget)
  if (allowedMenus.length > 0) {
    return allowedMenus
  }

  const fallbackMenus = sidebarMenus.filter((item) => !item.permission).map(mapMenuTarget)
  if (matchedMenu.value && !fallbackMenus.some((item) => item.key === matchedMenu.value.key)) {
    fallbackMenus.unshift(mapMenuTarget(matchedMenu.value))
  }

  return fallbackMenus.length > 0 ? fallbackMenus : sidebarMenus
})

const notificationBadgeVisible = computed(() => Number(notificationsUnreadCount.value || 0) > 0)
const symuseQrPanelTitle = computed(() => {
  if (symuseQrFlowState.value === 'confirm') {
    if (symuseQrConfirming.value) {
      return '正在确认桌面端登录'
    }
    return '确认桌面端登录'
  }
  if (symuseQrScanLoading.value) {
    return '正在识别登录二维码'
  }
  if (symuseQrScannerPending.value) {
    return '正在打开扫码器'
  }
  return '扫码后还需手机确认'
})

const symuseQrPanelDetail = computed(() => {
  if (symuseQrFlowState.value === 'confirm') {
    if (symuseQrConfirming.value) {
      return '请稍候，系统正在为当前桌面端完成授权。'
    }
    return '确认后将继续当前桌面端登录。'
  }
  if (symuseQrScanLoading.value) {
    return '识别成功后会进入二次确认，你可以选择确认登录或取消。'
  }
  return symuseQrScannerHint.value || '将二维码放入取景框中央，识别后会进入二次确认。'
})

const symuseQrStatusLabel = computed(() => {
  if (symuseQrConfirming.value) {
    return '正在确认'
  }
  if (symuseQrStatus.value === 'approved') {
    return '已确认'
  }
  if (symuseQrStatus.value === 'cancelled') {
    return '已取消'
  }
  return '待确认'
})

const symuseQrScannedAtLabel = computed(() => {
  const value = String(symuseQrScannedAt.value || '').trim()
  if (!value) {
    return ''
  }
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }
  return parsed.toLocaleString('zh-CN', {
    hour12: false,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
})

const activeMenu = computed(() => {
  return visibleMenus.value.find((item) => isActive(item)) || matchedMenu.value || visibleMenus.value[0] || sidebarMenus[0] || null
})

const searchFlatResults = computed(() => searchResultGroups.value.flatMap((group) => group.items))
const searchBodyVisible = computed(() => (
  Boolean(searchKeyword.value) && (searchResolved.value || (searchLoading.value && searchResultGroups.value.length > 0))
))
const searchBodyStyle = computed(() => ({
  height: searchBodyVisible.value ? `${searchBodyHeight.value}px` : '0px',
}))
const searchDistributionPositiveCount = computed(() => (
  searchDistributionInventories.value.filter((item) => Number(item.quantity || 0) > 0).length
))
const searchDistributionRows = computed(() => {
  const unitPrice = Number(searchDistributionItem.value?.price || 0)
  return [...searchDistributionInventories.value].sort((left, right) => {
    const quantityGap = Number(right.quantity || 0) - Number(left.quantity || 0)
    if (quantityGap !== 0) {
      return quantityGap
    }
    return String(left.shopName || '').localeCompare(String(right.shopName || ''), 'zh-CN')
  }).map((item) => ({
    ...item,
    unitPrice,
    lineAmount: unitPrice * Number(item.quantity || 0),
  }))
})
const searchDistributionTotalAmount = computed(() => (
  searchDistributionRows.value.reduce((sum, item) => sum + Number(item.lineAmount || 0), 0)
))
const searchDistributionTitle = computed(() => buildGoodsTitle(searchDistributionItem.value))
const searchDistributionSubtitle = computed(() => buildSearchSubtitle([
  normalizeSearchText(searchDistributionItem.value?.brand),
  normalizeSearchText(searchDistributionItem.value?.series),
  `有货点位 ${searchDistributionPositiveCount.value}`,
]))
const searchDistributionActionTitle = computed(() => (
  displayShopName(searchDistributionActionRow.value?.shopName || searchDistributionActionRow.value?.shopShortName) || '当前点位'
))
const searchDistributionActionSubtitle = computed(() => {
  const goodsLabel = buildGoodsTitle(searchDistributionItem.value)
  const sourceLabel = displayShopName(searchDistributionActionRow.value?.shopName || searchDistributionActionRow.value?.shopShortName) || '当前点位'
  if (Number(authStore.shopId || 0)) {
    return `已带入 ${goodsLabel} 与 ${sourceLabel}，调入点位可在工单中补选`
  }
  return `已带入 ${goodsLabel} 与 ${sourceLabel}`
})

const headerTitle = computed(() => {
  if (route.path === '/') {
    return `${resolveGreeting(greetingTick.value)}，${authStore.displayName || '欢迎回来'}`
  }
  if (route.name === 'log-center') {
    const logType = normalizeLogCenterType(route.query.type)
    return LOG_CENTER_TYPE_META[logType]?.label || '日志中心'
  }
  const routeTitle = String(route.meta?.headerTitle || '').trim()
  if (routeTitle) {
    return routeTitle
  }
  return activeMenu.value?.label || 'AQC'
})

const headerSubtitle = computed(() => {
  if (route.path === '/') {
    return formatToday(greetingTick.value)
  }
  if (route.name === 'log-center') {
    return '日志中心'
  }
  const routeSubtitle = String(route.meta?.headerSubtitle || '').trim()
  if (routeSubtitle) {
    return routeSubtitle
  }
  return activeMenu.value?.description || 'AQC 后台'
})

const themeLogoKey = computed(() => (themeStore.isDark ? 'dark' : 'light'))
const themeSensitiveLogoStyle = computed(() => ({
  filter: themeStore.isDark
    ? 'invert(1) brightness(1.08) drop-shadow(0 12px 28px rgba(0, 0, 0, 0.28))'
    : 'drop-shadow(0 12px 28px rgba(17, 17, 17, 0.12))',
}))

function parseSymuseQrLoginToken(rawValue) {
  const rawText = String(rawValue || '').trim()
  const prefix = 'SYMUSE_QR_LOGIN::'
  if (!rawText.startsWith(prefix)) {
    return ''
  }
  return rawText.slice(prefix.length).trim()
}

function resetSymuseQrState() {
  symuseQrFlowState.value = 'scanner'
  symuseQrSessionToken.value = ''
  symuseQrStatus.value = 'idle'
  symuseQrLastServiceLabel.value = ''
  symuseQrLastDeviceLabel.value = ''
  symuseQrScannedAt.value = ''
  symuseQrLoginOnceOnly.value = true
  symuseQrScanLoading.value = false
  symuseQrConfirming.value = false
  symuseQrCancelling.value = false
}

function applySymuseQrPayload(payload, fallbackStatus = 'scanned') {
  symuseQrLastServiceLabel.value = String(payload?.serviceLabel || '')
  symuseQrLastDeviceLabel.value = String(payload?.deviceLabel || '')
  symuseQrScannedAt.value = String(payload?.scannedAt || '')
  symuseQrStatus.value = String(payload?.status || fallbackStatus)
}

async function handleSymuseQrDetected(rawValue) {
  if (symuseQrScanLoading.value || symuseQrConfirming.value || symuseQrFlowState.value === 'confirm') {
    return
  }

  const sessionToken = parseSymuseQrLoginToken(rawValue)
  if (!sessionToken) {
    ElMessage.error('未识别到有效的桌面端登录二维码')
    await restartSymuseQrScanner()
    return
  }

  symuseQrScanLoading.value = true
  try {
    const scanPayload = await apiPost('/auth/symuse/qr/scan', { sessionToken }, {
      token: authStore.token,
    })
    if (!scanPayload?.success) {
      ElMessage.error(scanPayload?.message || '二维码校验失败')
      await restartSymuseQrScanner()
      return
    }

    applySymuseQrPayload(scanPayload)
    if (scanPayload.isExpired || ['expired', 'consumed', 'cancelled'].includes(String(scanPayload.status || ''))) {
      ElMessage.error(scanPayload.message || '二维码已失效，请刷新后重试')
      await restartSymuseQrScanner()
      return
    }

    symuseQrSessionToken.value = sessionToken
    symuseQrFlowState.value = 'confirm'
    symuseQrLoginOnceOnly.value = true
    await stopSymuseQrScanner()
  } catch (error) {
    console.error('Failed to scan QR login session', error)
    ElMessage.error('二维码校验失败，请稍后重试')
    await restartSymuseQrScanner()
  } finally {
    symuseQrScanLoading.value = false
  }
}

const {
  videoRef: symuseQrVideoRef,
  scanning: symuseQrScanning,
  scannerPending: symuseQrScannerPending,
  scannerHint: symuseQrScannerHint,
  startScanner: startSymuseQrScanner,
  stopScanner: stopSymuseQrScanner,
  focusScannerAt: focusSymuseQrScannerAt,
} = useBarcodeScanner({
  formats: [BarcodeFormat.QR_CODE],
  onDetected: handleSymuseQrDetected,
})

async function restartSymuseQrScanner() {
  if (!symuseQrLoginVisible.value) {
    return
  }
  symuseQrFlowState.value = 'scanner'
  await stopSymuseQrScanner()
  await nextTick()
  await startSymuseQrScanner()
}

async function confirmSymuseQrLoginRequest() {
  if (!symuseQrSessionToken.value || symuseQrConfirming.value || symuseQrCancelling.value) {
    return
  }

  symuseQrConfirming.value = true
  try {
    const approvePayload = await apiPost('/auth/symuse/qr/approve', {
      sessionToken: symuseQrSessionToken.value,
      loginOnceOnly: symuseQrLoginOnceOnly.value,
    }, {
      token: authStore.token,
    })
    if (!approvePayload?.success) {
      ElMessage.error(approvePayload?.message || '桌面端登录确认失败')
      return
    }

    symuseQrStatus.value = 'approved'
    ElMessage.success(approvePayload.message || '桌面端登录请求已确认')
    symuseQrLoginVisible.value = false
  } catch (error) {
    console.error('Failed to approve QR login session', error)
    ElMessage.error('桌面端登录确认失败，请稍后重试')
  } finally {
    symuseQrConfirming.value = false
  }
}

async function cancelSymuseQrLoginRequest(options = {}) {
  const { closeDialog = true, silent = false } = options

  if (!symuseQrSessionToken.value || symuseQrConfirming.value || symuseQrCancelling.value) {
    if (closeDialog) {
      symuseQrLoginVisible.value = false
    }
    return
  }

  symuseQrCancelling.value = true
  try {
    const cancelPayload = await apiPost('/auth/symuse/qr/cancel', { sessionToken: symuseQrSessionToken.value }, {
      token: authStore.token,
    })
    if (!cancelPayload?.success) {
      if (!silent) {
        ElMessage.error(cancelPayload?.message || '取消桌面端登录失败')
      }
      return
    }

    symuseQrStatus.value = 'cancelled'
    if (!silent) {
      ElMessage.success(cancelPayload.message || '桌面端登录请求已取消')
    }
    if (closeDialog) {
      symuseQrLoginVisible.value = false
    }
  } catch (error) {
    console.error('Failed to cancel QR login session', error)
    if (!silent) {
      ElMessage.error('取消桌面端登录失败，请稍后重试')
    }
  } finally {
    symuseQrCancelling.value = false
  }
}

function resolveGreeting(nowValue) {
  const minutes = getShanghaiMinutes(new Date(nowValue))

  if (minutes >= 330 && minutes < 540) return '早上好'
  if (minutes >= 540 && minutes < 690) return '上午好'
  if (minutes >= 690 && minutes < 840) return '中午好'
  if (minutes >= 840 && minutes < 1140) return '下午好'
  if (minutes >= 1140) return '晚上好'
  return '早点休息'
}

function formatToday(nowValue) {
  return formatShanghaiDate(new Date(nowValue), 'zh-CN', {
    month: 'long',
    day: 'numeric',
    weekday: 'long',
  })
}

function isActive(item) {
  if (item.key === 'sales-records' && route.name === 'repair-sales-records') {
    return true
  }
  if (item.key === 'sales-entry' && route.name === 'repair-sales-entry') {
    return true
  }
  const targetPath = typeof item.to === 'string' ? item.to : router.resolve(item.to).path
  if (targetPath === '/') {
    return route.path === '/'
  }
  return route.path.startsWith(targetPath)
}

function detectMobile() {
  const nextIsMobile = window.innerWidth < 980
  const mobileChanged = nextIsMobile !== isMobile.value
  isMobile.value = nextIsMobile

  if (isMobile.value) {
    sidebarCollapsed.value = false
    sidebarTextVisible.value = true
    sidebarFooterTextVisible.value = true
  } else {
    mobileOpen.value = false
    if (mobileChanged) {
      sidebarCollapsed.value = !sidebarDefaultExpanded.value
    }
    sidebarTextVisible.value = !sidebarCollapsed.value
    if (mobileChanged) {
      sidebarFooterTextVisible.value = !sidebarCollapsed.value
    }
  }
  if (settingsMenuVisible.value) {
    nextTick(() => {
      updateSettingsMenuPosition()
    })
  }
}

function clearSidebarTextTimer() {
  if (sidebarTextTimer) {
    window.clearTimeout(sidebarTextTimer)
    sidebarTextTimer = null
  }
}

function clearSidebarIntroTimer() {
  if (sidebarIntroTimer) {
    window.clearTimeout(sidebarIntroTimer)
    sidebarIntroTimer = null
  }
}

function clearChartResizeTimers() {
  chartResizeTimers.forEach((timerId) => window.clearTimeout(timerId))
  chartResizeTimers = []
}

function resetSidebarMenuScroll() {
  menuScrollRef.value?.scrollTo?.({ top: 0, left: 0, behavior: 'auto' })
}

function scheduleSidebarTextReveal() {
  clearSidebarTextTimer()
  if (isMobile.value) {
    sidebarTextVisible.value = true
    sidebarFooterTextVisible.value = true
    return
  }
  if (sidebarCollapsed.value) {
    sidebarTextVisible.value = false
    sidebarFooterTextVisible.value = false
    return
  }
  sidebarTextVisible.value = true
  sidebarFooterTextVisible.value = false
}

function scheduleSidebarIntroReveal() {
  clearSidebarIntroTimer()
  sidebarIntroVisible.value = false
  sidebarIntroTimer = window.setTimeout(() => {
    sidebarIntroVisible.value = true
    sidebarIntroTimer = null
  }, 120)
}

function syncChartLayoutDuringSidebarTransition() {
  clearChartResizeTimers()
  if (typeof window === 'undefined') {
    return
  }
  ;[0, 96, 180, 300, 420, 560].forEach((delay) => {
    const timerId = window.setTimeout(() => {
      window.dispatchEvent(new Event('resize'))
    }, delay)
    chartResizeTimers.push(timerId)
  })
}

function toggleSidebar() {
  if (isMobile.value) {
    mobileOpen.value = !mobileOpen.value
    return
  }
  resetSidebarMenuScroll()
  if (!sidebarCollapsed.value) {
    sidebarTextVisible.value = false
    sidebarFooterTextVisible.value = false
  }
  sidebarCollapsed.value = !sidebarCollapsed.value
  if (!sidebarCollapsed.value) {
    scheduleSidebarTextReveal()
  }
  syncChartLayoutDuringSidebarTransition()
}

function setSidebarDefaultExpanded(value) {
  const nextValue = Boolean(value)
  sidebarDefaultExpanded.value = nextValue
  persistSidebarDefaultExpanded(nextValue)
  if (isMobile.value) {
    return
  }
  if (nextValue) {
    sidebarCollapsed.value = false
    scheduleSidebarTextReveal()
  } else {
    sidebarCollapsed.value = true
    sidebarTextVisible.value = false
    sidebarFooterTextVisible.value = false
  }
  syncChartLayoutDuringSidebarTransition()
}

function handleSidebarTransitionEnd(event) {
  if (isMobile.value || sidebarCollapsed.value) {
    return
  }
  if (event?.target !== event?.currentTarget) {
    return
  }
  if (event.propertyName !== 'width') {
    return
  }
  sidebarFooterTextVisible.value = true
}

function handleMenuClick() {
  if (isMobile.value) {
    mobileOpen.value = false
  }
}

function resolveElementRef(target) {
  if (!target) {
    return null
  }
  if (target instanceof HTMLElement) {
    return target
  }
  if (target.$el instanceof HTMLElement) {
    return target.$el
  }
  return null
}

function buildFloatingMenuPosition(buttonRefValue) {
  if (typeof window === 'undefined') {
    return null
  }
  const anchorElement = resolveElementRef(buttonRefValue)
  if (!anchorElement) {
    return null
  }
  const rect = anchorElement.getBoundingClientRect()
  const viewportWidth = Math.max(window.innerWidth || 0, 320)
  const menuWidth = Math.min(320, Math.max(260, viewportWidth - 24))
  const maxLeft = Math.max(12, viewportWidth - menuWidth - 12)
  const left = Math.min(Math.max(12, rect.right - menuWidth), maxLeft)
  return {
    top: `${Math.round(rect.bottom + SETTINGS_MENU_OFFSET)}px`,
    left: `${Math.round(left)}px`,
    width: `${Math.round(Math.min(menuWidth, viewportWidth - 24))}px`,
  }
}

function updateSettingsMenuPosition() {
  const nextStyle = buildFloatingMenuPosition(settingsAnchorRef.value)
  if (nextStyle) {
    settingsMenuStyle.value = nextStyle
  }
}

function openSettingsMenu() {
  settingsMenuVisible.value = true
  nextTick(() => {
    updateSettingsMenuPosition()
  })
}

function setThemeMode(mode) {
  headerPanelSection.value = 'settings'
  themeStore.setMode(mode)
}

function switchHeaderPanelSection(section) {
  const changed = headerPanelSection.value !== section
  headerPanelSection.value = section
  nextTick(() => {
    updateSettingsMenuPosition()
  })
  return changed
}

function openSettingsSection() {
  switchHeaderPanelSection('settings')
}

function openNotificationSection() {
  const changed = switchHeaderPanelSection('notifications')
  if (changed || (!notificationLoading.value && !notifications.length)) {
    void loadNotifications({ silent: true })
  }
}

function closeSettingsMenu() {
  settingsMenuVisible.value = false
}

function toggleSettingsMenu() {
  if (settingsMenuVisible.value) {
    closeSettingsMenu()
    return
  }
  headerPanelSection.value = 'settings'
  openSettingsMenu()
}

function normalizeSearchText(value) {
  return String(value || '').trim()
}

function buildSearchGroup(key, label, icon, items) {
  const normalizedItems = items.filter(Boolean)
  if (!normalizedItems.length) {
    return null
  }
  return { key, label, icon, items: normalizedItems }
}

function buildSearchSubtitle(parts) {
  return parts
    .map((part) => normalizeSearchText(part))
    .filter(Boolean)
    .join(' · ')
}

function buildGoodsTitle(item) {
  return [item.brand, item.series, item.model]
    .map((value) => normalizeSearchText(value))
    .filter(Boolean)
    .join(' ') || normalizeSearchText(item.name) || '未命名商品'
}

const globalSearchMoneyFormatter = new Intl.NumberFormat('zh-CN', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

function formatMoney(value) {
  return globalSearchMoneyFormatter.format(Number(value || 0))
}

function formatSearchDistributionShopType(shopType) {
  return Number(shopType || 0) === SHOP_TYPE_WAREHOUSE
    ? '仓库'
    : Number(shopType || 0) === SHOP_TYPE_OTHER_WAREHOUSE
      ? '其他仓库'
      : Number(shopType || 0) === SHOP_TYPE_REPAIR
        ? '维修点'
        : '店铺'
}

function primeSearchDistributionState(payload) {
  searchDistributionItem.value = payload?.item || null
  searchDistributionInventories.value = (payload?.inventories || []).map((item) => normalizeLocationRow(item, item.shopType))
  searchDistributionTotalStock.value = Number(payload?.totalStock || 0)
}

function searchDistributionTableSummary({ columns, data }) {
  const totalQuantity = data.reduce((sum, item) => sum + Number(item.quantity || 0), 0)
  const totalAmount = data.reduce((sum, item) => sum + Number(item.lineAmount || 0), 0)
  return columns.map((column, index) => {
    if (index === 0) {
      return '合计'
    }
    if (column.property === 'quantity') {
      return String(totalQuantity)
    }
    if (column.property === 'lineAmount') {
      return `¥ ${formatMoney(totalAmount)}`
    }
    return ''
  })
}

async function openGlobalSearchDistribution(itemId) {
  const normalizedId = Number(itemId || 0)
  if (!normalizedId) {
    ElMessage.warning('当前商品信息未准备完成')
    return
  }
  searchDistributionActionMenuVisible.value = false
  searchDistributionActionRow.value = null
  searchDistributionVisible.value = true
  searchDistributionLoading.value = true
  const payload = await apiGet(`/goods/items/${normalizedId}/inventory`, {
    token: authStore.token,
    timeoutMs: 12000,
  })
  searchDistributionLoading.value = false
  if (!payload?.success) {
    searchDistributionVisible.value = false
    ElMessage.error(payload?.message || '商品分布加载失败')
    return
  }
  primeSearchDistributionState(payload)
}

async function openGlobalSearchDistributionInventoryLog() {
  const goodsId = Number(searchDistributionItem.value?.id || 0)
  if (!goodsId) {
    ElMessage.warning('当前商品信息未准备完成')
    return
  }
  searchDistributionActionMenuVisible.value = false
  searchDistributionVisible.value = false
  await router.push({
    name: 'log-center',
    query: buildLogCenterQuery({
      type: 'goods_inventory',
      item_id: String(goodsId),
      subject_name: buildGoodsTitle(searchDistributionItem.value),
      back: route.fullPath,
    }),
  })
}

function openSearchDistributionActionMenu(row) {
  if (!row?.shopId) {
    ElMessage.warning('当前点位信息未准备完成')
    return
  }
  if (!searchDistributionItem.value?.id) {
    ElMessage.warning('当前商品信息未准备完成')
    return
  }
  searchDistributionActionRow.value = row
  if (isMobileViewport.value) {
    searchDistributionVisible.value = false
    nextTick(() => {
      searchDistributionActionMenuVisible.value = true
    })
    return
  }
  searchDistributionActionMenuVisible.value = true
}

async function createTransferFromSearchDistribution() {
  const sourceShopId = Number(searchDistributionActionRow.value?.shopId || 0)
  const goodsId = Number(searchDistributionItem.value?.id || 0)
  if (!sourceShopId || !goodsId) {
    ElMessage.warning('当前商品分布信息未准备完成')
    return
  }
  const defaultTargetShopId = Number(authStore.shopId || 0) || null
  const nextQuery = {
    compose: '1',
    type: 'transfer',
    prefill_source_shop_id: String(sourceShopId),
    prefill_goods_id: String(goodsId),
  }
  if (defaultTargetShopId && defaultTargetShopId !== sourceShopId) {
    nextQuery.prefill_target_shop_id = String(defaultTargetShopId)
  }
  searchDistributionActionMenuVisible.value = false
  searchDistributionVisible.value = false
  searchVisible.value = false
  resetMobileSheetStackSeed()
  if (isMobileViewport.value) {
    await new Promise((resolve) => window.setTimeout(resolve, 460))
  } else {
    await nextTick()
  }
  await router.push({ name: 'work-orders', query: nextQuery })
  if (!defaultTargetShopId) {
    ElMessage.info('已带入商品和调出点位，请在工单中补选调入店铺 / 仓库')
    return
  }
  if (defaultTargetShopId === sourceShopId) {
    ElMessage.warning('已带入商品和调出点位，当前账号默认店铺与调出点位相同，请在工单中改选调入店铺 / 仓库')
  }
}

function resetMobileSheetStackSeed() {
  if (typeof window === 'undefined') {
    return
  }
  window.__aqcMobileSheetZIndexSeed = 2600
}

async function viewSearchDistributionInventoryLogs() {
  const sourceShopId = Number(searchDistributionActionRow.value?.shopId || 0)
  const goodsId = Number(searchDistributionItem.value?.id || 0)
  if (!sourceShopId || !goodsId) {
    ElMessage.warning('当前商品分布信息未准备完成')
    return
  }
  const goodsLabel = buildGoodsTitle(searchDistributionItem.value)
  const sourceLabel = displayShopName(searchDistributionActionRow.value?.shopName || searchDistributionActionRow.value?.shopShortName) || '当前点位'
  searchDistributionActionMenuVisible.value = false
  searchDistributionVisible.value = false
  searchVisible.value = false
  if (isMobileViewport.value) {
    await new Promise((resolve) => window.setTimeout(resolve, 460))
  } else {
    await nextTick()
  }
  await router.push({
    name: 'log-center',
    query: buildLogCenterQuery({
      type: 'goods_inventory',
      item_id: String(goodsId),
      shop_id: String(sourceShopId),
      subject_name: `${sourceLabel} · ${goodsLabel}`,
      back: route.fullPath,
    }),
  })
}

function updateActiveSearchResult() {
  const firstKey = searchFlatResults.value[0]?.key || ''
  if (!searchFlatResults.value.some((item) => item.key === activeSearchKey.value)) {
    activeSearchKey.value = firstKey
  }
}

function refreshSearchBodyHeight() {
  nextTick(() => {
    const content = searchBodyContentRef.value
    if (!searchBodyVisible.value) {
      searchBodyHeight.value = 0
      return
    }
    if (!content) {
      return
    }
    searchBodyHeight.value = Math.ceil(content.scrollHeight || 0)
  })
}

async function runGlobalSearch(keywordValue) {
  const keyword = normalizeSearchText(keywordValue)
  if (!keyword) {
    searchResultGroups.value = []
    activeSearchKey.value = ''
    searchLoading.value = false
    searchResolved.value = false
    searchBodyHeight.value = 0
    searchResultVersion.value = 0
    if (searchAbortController) {
      searchAbortController.abort()
      searchAbortController = null
    }
    return
  }

  if (searchAbortController) {
    searchAbortController.abort()
  }
  searchAbortController = new AbortController()
  searchLoading.value = true

  const commonOptions = {
    token: authStore.token,
    signal: searchAbortController.signal,
    timeoutMs: 12000,
  }

  const [goodsPayload, distributionPayload, salesPayload, orderPayload, workOrderPayload, shopPayload] = await Promise.all([
    apiGet('/goods/items', {
      ...commonOptions,
      query: { page: 1, page_size: SEARCH_LIMIT, q: keyword, catalog_only: 'false' },
    }),
    apiGet('/goods/items', {
      ...commonOptions,
      query: { page: 1, page_size: SEARCH_LIMIT, q: keyword, catalog_only: 'false', has_stock: 'true' },
    }),
    apiGet('/sales/records', {
      ...commonOptions,
      query: { page: 1, page_size: SEARCH_LIMIT, q: keyword },
    }),
    apiGet('/orders', {
      ...commonOptions,
      query: { page: 1, page_size: SEARCH_LIMIT, q: keyword },
    }),
    apiGet('/work-orders', {
      ...commonOptions,
      query: { page: 1, page_size: SEARCH_LIMIT, keyword, scope: authStore.isAdmin ? 'all' : 'mine' },
    }),
    apiGet('/shops', {
      ...commonOptions,
      query: { page: 1, page_size: SEARCH_LIMIT, q: keyword },
    }),
  ])

  if (searchAbortController?.signal.aborted) {
    return
  }

  const groups = [
    buildSearchGroup(
      'distribution',
      '库存分布',
      searchTypeIcons.distribution,
      (distributionPayload?.items || []).map((item) => ({
        key: `distribution-${item.id}`,
        title: buildGoodsTitle(item),
        badge: `库存 ${item.stock ?? 0}`,
        subtitle: buildSearchSubtitle([item.barcode ? `条码 ${item.barcode}` : '']),
        action: () => openGlobalSearchDistribution(item.id),
      })),
    ),
    buildSearchGroup(
      'goods',
      '商品',
      searchTypeIcons.goods,
      (goodsPayload?.items || []).map((item) => ({
        key: `goods-${item.id}`,
        title: buildGoodsTitle(item),
        badge: '',
        subtitle: buildSearchSubtitle([item.barcode ? `条码 ${item.barcode}` : '', `总库存 ${item.stock ?? 0}`]),
        to: { name: 'goods-manage', query: { spotlight_goods: String(item.id) } },
      })),
    ),
    buildSearchGroup(
      'sales',
      '销售记录',
      searchTypeIcons.sales,
      (salesPayload?.records || []).map((item) => ({
        key: `sales-${item.id}`,
        title: item.goodsDisplayName || item.orderNum || '销售记录',
        badge: item.orderNum ? `订单 ${item.orderNum}` : '',
        subtitle: buildSearchSubtitle([item.shopName, item.salesperson, `¥ ${Number(item.amount || 0).toFixed(2)}`]),
        to: { name: 'sales-records', query: { spotlight_sale_record: String(item.id) } },
      })),
    ),
    buildSearchGroup(
      'orders',
      '订单',
      searchTypeIcons.orders,
      (orderPayload?.orders || []).map((item) => ({
        key: `orders-${item.id}`,
        title: item.orderNum || `订单 #${item.id}`,
        badge: item.userName || item.recipientName || '',
        subtitle: buildSearchSubtitle([item.goodsSummary, item.recipientPhone, `¥ ${Number(item.totalFee || item.total || 0).toFixed(2)}`]),
        to: { name: 'orders', query: { keyword: String(item.orderNum || '') } },
      })),
    ),
    buildSearchGroup(
      'workOrders',
      '工单',
      searchTypeIcons.workOrders,
      (workOrderPayload?.orders || []).map((item) => ({
        key: `work-orders-${item.id}`,
        title: item.orderNum || item.orderTypeLabel || '工单',
        badge: item.statusLabel || '',
        subtitle: buildSearchSubtitle([item.orderTypeLabel, item.reason, item.formDate]),
        to: {
          name: 'work-orders',
          query: {
            scope: authStore.isAdmin ? 'all' : 'mine',
            keyword: String(item.orderNum || ''),
            spotlight_work_order: String(item.id),
          },
        },
      })),
    ),
    buildSearchGroup(
      'shops',
      '店铺/仓库',
      searchTypeIcons.shops,
      (shopPayload?.shops || []).map((item) => ({
        key: `shops-${item.id}`,
        title: item.name || '未命名店铺',
        badge: item.shopType === 1 ? '仓库' : item.shopType === 2 ? '其他仓库' : '店铺',
        subtitle: buildSearchSubtitle([item.managerName, item.phone, item.address]),
        to: { name: 'shops-manage', query: { spotlight_shop: String(item.id) } },
      })),
    ),
  ].filter(Boolean)

  searchResultGroups.value = groups
  searchResultVersion.value += 1
  updateActiveSearchResult()
  searchLoading.value = false
  searchResolved.value = true
  refreshSearchBodyHeight()
  window.requestAnimationFrame(() => {
    refreshSearchBodyHeight()
  })
}

function moveSearchSelection(step) {
  if (!searchFlatResults.value.length) {
    return
  }
  const currentIndex = searchFlatResults.value.findIndex((item) => item.key === activeSearchKey.value)
  const nextIndex = currentIndex < 0
    ? 0
    : (currentIndex + step + searchFlatResults.value.length) % searchFlatResults.value.length
  activeSearchKey.value = searchFlatResults.value[nextIndex]?.key || searchFlatResults.value[0].key
}

async function openSearchResult(item) {
  if (typeof item?.action === 'function') {
    preserveSearchDistributionOnClose.value = true
    searchVisible.value = false
    await nextTick()
    await item.action()
    return
  }
  if (!item?.to) {
    return
  }
  searchVisible.value = false
  await router.push(item.to)
}

function openActiveSearchResult() {
  const current = searchFlatResults.value.find((item) => item.key === activeSearchKey.value) || searchFlatResults.value[0]
  if (current) {
    void openSearchResult(current)
  }
}

function handleGlobalSearchEnter(event) {
  if (isMobile.value) {
    event?.target?.blur?.()
    return
  }
  openActiveSearchResult()
}

function openGlobalSearch() {
  searchVisible.value = true
  closeSettingsMenu()
  focusGlobalSearchInput()
}

function openUpdateLogDialog() {
  updateLogVisible.value = true
  closeSettingsMenu()
  void loadUpdateLog()
}

function openSymuseQrLoginDialog() {
  resetSymuseQrState()
  symuseQrLoginVisible.value = true
  closeSettingsMenu()
}

function refreshUpdateLog() {
  void loadUpdateLog({ force: true })
}

async function openUpdateLogHistory() {
  updateLogVisible.value = false
  await router.push({
    name: 'log-center',
    query: {
      type: 'update',
      back: route.fullPath,
    },
  })
}

function upgradeToLatestVersion() {
  appVersionStore.upgradeToLatestVersion()
}

function syncNotificationPermission() {
  if (typeof window === 'undefined' || typeof Notification === 'undefined') {
    notificationSupported.value = false
    notificationPermission.value = 'unsupported'
    return
  }
  notificationSupported.value = true
  notificationPermission.value = Notification.permission
}

function sendBrowserNotification(title, body) {
  if (typeof window === 'undefined' || typeof Notification === 'undefined') {
    return null
  }
  if (Notification.permission !== 'granted') {
    return null
  }
  const notification = new Notification(title, {
    body,
    tag: 'aqc-header-notification',
  })
  notification.onclick = () => {
    window.focus()
    notification.close()
  }
  return notification
}

function formatNotificationTypeLabel(item) {
  return NOTIFICATION_TYPE_LABELS[String(item?.notificationType || '').trim()] || '系统通知'
}

function formatNotificationTime(value) {
  if (!value) {
    return ''
  }
  const text = String(value || '').trim()
  const normalized = text.includes('T') ? text : text.replace(' ', 'T')
  const hasExplicitTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(normalized)
  const parsed = new Date(hasExplicitTimezone ? normalized : `${normalized}+08:00`)
  if (Number.isNaN(parsed.getTime())) {
    return text
  }
  return formatShanghaiDate(parsed)
}

function buildNotificationDetail(item) {
  const detailParts = [
    String(item?.content || '').trim(),
    String(item?.createdByName || '').trim(),
  ].filter(Boolean)
  const detail = detailParts.join(' · ')
  return detail || ''
}

async function requestBrowserNotifications() {
  if (typeof window === 'undefined' || typeof Notification === 'undefined') {
    ElMessage.warning('当前浏览器不支持系统通知')
    return
  }
  notificationRequesting.value = true
  try {
    const permission = await Notification.requestPermission()
    notificationPermission.value = permission
    if (permission === 'granted') {
      sendBrowserNotification('AQC-N 通知已开启', '浏览器通知已接通，后续系统提醒会从这里发出。')
      ElMessage.success('浏览器通知已开启')
      return
    }
    ElMessage.warning(permission === 'denied' ? '浏览器通知已被拒绝' : '未开启浏览器通知')
  } finally {
    notificationRequesting.value = false
  }
}

async function loadNotifications({ silent = false } = {}) {
  if (notificationLoading.value) {
    return
  }
  notificationLoading.value = true
  try {
    const payload = await apiGet('/notifications', {
      token: authStore.token,
      query: {
        page: 1,
        page_size: 12,
      },
    })
    if (!payload?.success) {
      notifications.value = []
      notificationsUnreadCount.value = 0
      if (!silent) {
        ElMessage.error(payload?.message || '通知加载失败')
      }
      return
    }
    notifications.value = payload.notifications || []
    notificationsUnreadCount.value = Number(payload.unreadCount || 0)
    if (
      notificationsUnreadCount.value > lastBrowserUnreadCount
      && notificationPermission.value === 'granted'
    ) {
      sendBrowserNotification('AQC-N 新通知', `你有 ${notificationsUnreadCount.value} 条待处理通知。`)
    }
    lastBrowserUnreadCount = notificationsUnreadCount.value
  } catch (error) {
    console.error('Notification load failed', error)
    if (!silent) {
      ElMessage.error('通知加载失败')
    }
  } finally {
    notificationLoading.value = false
  }
}

async function respondNotification(item, accepted) {
  const result = await apiPost(
    `/notifications/${item.id}/respond`,
    { accepted },
    { token: authStore.token },
  )
  if (!result?.success) {
    ElMessage.error(result?.message || '通知处理失败')
    return
  }
  ElMessage.success(result.message || '通知已处理')
  await loadNotifications({ silent: true })
}

async function openReportNotification(item) {
  if (!item?.relatedId) {
    ElMessage.warning('当前报告通知缺少报告内容')
    return
  }
  await apiPost(`/notifications/${item.id}/read`, {}, { token: authStore.token })
  await loadNotifications({ silent: true })
  closeSettingsMenu()
  await router.push({
    name: 'reports',
    query: {
      report_id: String(item.relatedId),
      from_notification: '1',
      back: route.fullPath,
    },
  })
}

async function dismissNotification(item) {
  const result = await apiPost(`/notifications/${item.id}/dismiss`, {}, { token: authStore.token })
  if (!result?.success) {
    ElMessage.error(result?.message || '通知关闭失败')
    return
  }
  ElMessage.success(result.message || '通知已关闭')
  await loadNotifications({ silent: true })
}

function focusGlobalSearchInput() {
  if (isMobileViewport.value || isMobile.value) {
    clearSearchFocusTimers()
    return
  }
  clearSearchFocusTimers()
  nextTick(() => {
    focusGlobalSearchInputElement()
  })
}

function focusGlobalSearchInputElement() {
  const focusTarget = searchInputRef.value
  if (!focusTarget) {
    return
  }
  try {
    focusTarget.focus({ preventScroll: true })
  } catch {
    focusTarget.focus?.()
  }
  const cursorAt = String(focusTarget.value || '').length
  focusTarget.setSelectionRange?.(cursorAt, cursorAt)
}

function clearSearchFocusTimers() {
  searchFocusRetryTimers.forEach((timerId) => window.clearTimeout(timerId))
  searchFocusRetryTimers = []
}

function handleOpenGlobalSearchEvent() {
  openGlobalSearch()
}

function handleGlobalKeydown(event) {
  if ((event.metaKey || event.ctrlKey) && String(event.key || '').toLowerCase() === 'k') {
    event.preventDefault()
    openGlobalSearch()
    return
  }
  if (event.key === 'Escape') {
    closeSettingsMenu()
  }
}

watch(
  () => route.path,
  async () => {
    closeSettingsMenu()
    searchVisible.value = false
    await nextTick()
    contentRef.value?.scrollTo?.({ top: 0, left: 0, behavior: 'auto' })
  },
)

watch(settingsMenuVisible, (value) => {
  if (!value) {
    headerPanelSection.value = 'settings'
    return
  }
  nextTick(() => {
    updateSettingsMenuPosition()
  })
})

watch(searchVisible, (value) => {
  if (value) {
    focusGlobalSearchInput()
    return
  }
  clearSearchFocusTimers()
  if (preserveSearchDistributionOnClose.value) {
    preserveSearchDistributionOnClose.value = false
  } else {
    searchDistributionVisible.value = false
  }
  searchKeyword.value = ''
  searchResultGroups.value = []
  activeSearchKey.value = ''
  searchLoading.value = false
  searchResolved.value = false
  searchBodyHeight.value = 0
  searchResultVersion.value = 0
  if (searchDebounceTimer) {
    window.clearTimeout(searchDebounceTimer)
    searchDebounceTimer = null
  }
  if (searchAbortController) {
    searchAbortController.abort()
    searchAbortController = null
  }
})

watch(searchKeyword, (value) => {
  if (searchDebounceTimer) {
    window.clearTimeout(searchDebounceTimer)
  }
  const keyword = normalizeSearchText(value)
  if (!keyword) {
    void runGlobalSearch('')
    return
  }
  searchDebounceTimer = window.setTimeout(() => {
    void runGlobalSearch(keyword)
  }, 180)
})

watch(searchResultGroups, () => {
  refreshSearchBodyHeight()
}, { deep: true })

watch(searchBodyVisible, () => {
  refreshSearchBodyHeight()
})

watch(symuseQrLoginVisible, async (value) => {
  if (value) {
    resetSymuseQrState()
    await nextTick()
    await startSymuseQrScanner()
    return
  }
  if (symuseQrFlowState.value === 'confirm' && symuseQrSessionToken.value && symuseQrStatus.value === 'scanned' && !symuseQrConfirming.value) {
    await cancelSymuseQrLoginRequest({ closeDialog: false, silent: true })
  }
  await stopSymuseQrScanner()
  resetSymuseQrState()
})

async function onLogout() {
  closeSettingsMenu()
  try {
    await confirmAction('确认退出当前登录账号吗？', '退出确认', '退出')
  } catch {
    return
  }

  clearStoredLoginState()
  clearStoredPostLoginPath()
  await authStore.logout()
  const returnTo = buildSymuseLogoutReturnTo()
  const target = `https://account.symuse.com/logout?return_to=${encodeURIComponent(returnTo)}`
  window.location.replace(target)
}

onMounted(() => {
  detectMobile()
  scheduleSidebarIntroReveal()
  scheduleSidebarTextReveal()
  resetSidebarMenuScroll()
  syncNotificationPermission()
  void loadNotifications({ silent: true })
  window.addEventListener('resize', detectMobile)
  window.addEventListener('aqc:open-global-search', handleOpenGlobalSearchEvent)
  document.addEventListener('keydown', handleGlobalKeydown)
  greetingTimer = window.setInterval(() => {
    greetingTick.value = Date.now()
  }, 30000)
  notificationRefreshTimer = window.setInterval(() => {
    void loadNotifications({ silent: true })
  }, 60000)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', detectMobile)
  window.removeEventListener('aqc:open-global-search', handleOpenGlobalSearchEvent)
  document.removeEventListener('keydown', handleGlobalKeydown)
  clearSidebarIntroTimer()
  clearSidebarTextTimer()
  clearChartResizeTimers()
  clearSearchFocusTimers()
  if (searchDebounceTimer) {
    window.clearTimeout(searchDebounceTimer)
    searchDebounceTimer = null
  }
  if (searchAbortController) {
    searchAbortController.abort()
    searchAbortController = null
  }
  if (greetingTimer) {
    clearInterval(greetingTimer)
    greetingTimer = null
  }
  if (notificationRefreshTimer) {
    clearInterval(notificationRefreshTimer)
    notificationRefreshTimer = null
  }
  stopSymuseQrScanner()
})
</script>
