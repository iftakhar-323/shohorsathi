import { AuthPage, ChatPage, NotificationsPage, RequireAuth, t } from "@shohor/web-core";
import { Route, Routes } from "react-router-dom";

import Footer from "./components/Footer";
import Header from "./components/Header";
import Cart from "./pages/Cart";
import Checkout from "./pages/Checkout";
import { CustomRequestDetail, CustomRequestList, NewCustomRequest } from "./pages/CustomRequests";
import Community from "./pages/Community";
import Home from "./pages/Home";
import { IssueDetail, IssuesHome, ReportIssue } from "./pages/Issues";
import NotFound from "./pages/NotFound";
import OrderDetail from "./pages/OrderDetail";
import Orders from "./pages/Orders";
import PaymentResult from "./pages/PaymentResult";
import Profile from "./pages/Profile";
import ServiceDetail from "./pages/ServiceDetail";
import Services from "./pages/Services";
import Shop from "./pages/Shop";
import { MySubscriptions, Subscribe, SubscriptionDetail, SubscriptionPlans } from "./pages/Subscriptions";

function Private({ children }: { children: React.ReactNode }) {
  return <RequireAuth>{children}</RequireAuth>;
}

export default function App() {
  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<AuthPage appName={t("শহরসাথী")} />} />
          <Route path="/register" element={<AuthPage appName={t("শহরসাথী")} initialMode="register" />} />
          <Route path="/services" element={<Services />} />
          <Route path="/services/:slug" element={<ServiceDetail />} />
          <Route path="/shop" element={<Shop />} />
          <Route path="/cart" element={<Private><Cart /></Private>} />
          <Route path="/checkout" element={<Private><Checkout /></Private>} />
          <Route path="/orders" element={<Private><Orders /></Private>} />
          <Route path="/orders/:id" element={<Private><OrderDetail /></Private>} />
          <Route path="/custom-requests" element={<Private><CustomRequestList /></Private>} />
          <Route path="/custom-requests/new" element={<Private><NewCustomRequest /></Private>} />
          <Route path="/custom-requests/:id" element={<Private><CustomRequestDetail /></Private>} />
          <Route path="/profile" element={<Private><Profile /></Private>} />
          <Route path="/subscriptions" element={<SubscriptionPlans />} />
          <Route path="/subscriptions/new/:slug" element={<Subscribe />} />
          <Route path="/subscriptions/mine" element={<Private><MySubscriptions /></Private>} />
          <Route path="/subscriptions/:id" element={<Private><SubscriptionDetail /></Private>} />
          <Route path="/payment/result" element={<PaymentResult />} />
          <Route path="/issues" element={<IssuesHome />} />
          <Route path="/issues/new" element={<Private><ReportIssue /></Private>} />
          <Route path="/issues/mine" element={<Private><IssuesHome mine /></Private>} />
          <Route path="/issues/:id" element={<IssueDetail />} />
          <Route path="/community" element={<Community />} />
          <Route path="/chat" element={<Private><div className="mx-auto max-w-[1200px] px-4 py-8 sm:px-6"><ChatPage /></div></Private>} />
          <Route path="/chat/:id" element={<Private><div className="mx-auto max-w-[1200px] px-4 py-8 sm:px-6"><ChatPage /></div></Private>} />
          <Route path="/notifications" element={<Private><div className="px-4 py-8 sm:px-6"><NotificationsPage /></div></Private>} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
      <Footer />
    </div>
  );
}
