import Vue from 'vue'
import VueCompositionAPI from '@vue/composition-api'
import App from './App.vue'

Vue.config.productionTip = false
Vue.use(VueCompositionAPI)

App.mpType = 'app'

const app = new Vue({
  ...App,
})

app.$mount()
