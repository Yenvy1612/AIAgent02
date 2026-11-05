import { ChevronDown } from 'lucide-react';
import EmergencyButton from './EmergencyButton.jsx';

export default function Topbar({ title, profiles, profileId, onChangeProfile }) {
  return <header className="topbar">
    <div className="breadcrumbs"><span>DiaCare AI</span><span className="crumb-slash" aria-hidden="true">/</span><strong>{title}</strong></div>
    <div className="topbar-actions">
      <label className="profile-select-wrap">
        Hồ sơ mô phỏng
        <select value={profileId} onChange={(event) => onChangeProfile(event.target.value)}>
          {profiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.id} · {profile.age} tuổi</option>)}
        </select>
        <ChevronDown className="select-chevron" size={18} />
      </label>
      <EmergencyButton />
    </div>
  </header>;
}
