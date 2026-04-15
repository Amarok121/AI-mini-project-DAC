import { createApp } from "vue";
import { createRouter, createWebHistory } from "vue-router";
import App from "./App.vue";
import Home from "./views/Home.vue";
import Report from "./views/Report.vue";
import JobStatus from "./views/JobStatus.vue";
import "./styles.css";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", component: Home },
    { path: "/report", component: Report },
    { path: "/job", component: JobStatus }
  ]
});

createApp(App).use(router).mount("#app");

