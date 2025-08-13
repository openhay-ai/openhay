import { useLocation } from "react-router-dom";
import Index from "./Index";
import FeatureChat from "./FeatureChat";

const Root = () => {
  const location = useLocation();
  const hasType = new URLSearchParams(location.search).has("type");
  const hasQuery = new URLSearchParams(location.search).has("q");

  // If a type or q is present, show chat mode on root; otherwise show landing page
  if (hasType || hasQuery) {
    return <FeatureChat />;
  }
  return <Index />;
};

export default Root;


