import {createRoot} from 'react-dom/client';
import App from './App';
import {InvestorDemo} from './InvestorDemo';
import './style.css';
createRoot(document.getElementById('root')!).render(window.location.pathname==='/investor-demo'?<InvestorDemo/>:<App/>);
