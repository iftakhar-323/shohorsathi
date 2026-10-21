import { AuthPage, RequireAuth } from "@shohor/web-core";
import { Route, Routes } from "react-router-dom";

import Footer from "./components/Footer";
import Header from "./components/Header";
import Cart from "./pages/Cart";
import Checkout from "./pages/Checkout";
import { CustomRequestDetail, CustomRequestList, NewCustomRequest } from "./pages/CustomRequests";
import Home from "./pages/Home";
import NotFound from "./pages/NotFound";
import OrderDetail from "./pages/OrderDetail";
import Orders from "./pages/Orders";
import Profile from "./pages/Profile";
import ServiceDetail from "./pages/ServiceDetail";
import Services from "./pages/Services";
import Shop from "./pages/Shop";

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
          <Route path="/login" element={<AuthPage appName="শহরসাথী" />} />
          <Route path="/register" element={<AuthPage appName="শহরসাথী" initialMode="register" />} />
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
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
      <Footer />
    </div>
  );
}
