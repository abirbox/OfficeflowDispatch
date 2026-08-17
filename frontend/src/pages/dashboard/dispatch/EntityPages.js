import EntityCrudPage from './EntityCrudPage';

export const ClientsPage = () => (
  <EntityCrudPage
    title="Clients" endpoint="/dispatch/clients" permBase="dispatch.clients"
    columns={[{ key: 'name', label: 'Name' }, { key: 'code', label: 'Code' }, { key: 'contact_person', label: 'Contact' }, { key: 'contact_number', label: 'Phone' }, { key: 'city', label: 'City' }]}
    fields={[
      { key: 'name', label: 'Name', required: true },
      { key: 'code', label: 'Code' },
      { key: 'contact_person', label: 'Contact Person' },
      { key: 'contact_number', label: 'Contact Number' },
      { key: 'email', label: 'Email' },
      { key: 'website', label: 'Website' },
      { key: 'address', label: 'Address' },
      { key: 'city', label: 'City' },
      { key: 'location', label: 'Location' },
      { key: 'notes', label: 'Notes', type: 'textarea' },
    ]}
  />
);

export const VendorsPage = () => (
  <EntityCrudPage
    title="Vendors" endpoint="/dispatch/vendors" permBase="dispatch.vendors"
    columns={[{ key: 'name', label: 'Name' }, { key: 'code', label: 'Code' }, { key: 'contact_person', label: 'Contact' }, { key: 'contact_number', label: 'Phone' }, { key: 'city', label: 'City' }]}
    fields={[
      { key: 'name', label: 'Name', required: true },
      { key: 'code', label: 'Code' },
      { key: 'contact_person', label: 'Contact Person' },
      { key: 'contact_number', label: 'Contact Number' },
      { key: 'email', label: 'Email' },
      { key: 'website', label: 'Website' },
      { key: 'address', label: 'Address' },
      { key: 'city', label: 'City' },
      { key: 'location', label: 'Location' },
      { key: 'notes', label: 'Notes', type: 'textarea' },
    ]}
  />
);

export const OfficersPage = () => (
  <EntityCrudPage
    title="Security Officers" endpoint="/dispatch/officers" permBase="dispatch.officers"
    columns={[{ key: 'name', label: 'Name' }, { key: 'officer_code', label: 'Code' }, { key: 'contact_number', label: 'Phone' }, { key: 'email', label: 'Email' }]}
    fields={[
      { key: 'name', label: 'Name', required: true },
      { key: 'officer_code', label: 'Officer Code' },
      { key: 'contact_number', label: 'Contact Number' },
      { key: 'alternate_contact_number', label: 'Alternate Number' },
      { key: 'email', label: 'Email' },
      { key: 'vendor_id', label: 'Vendor', select: 'vendors' },
      { key: 'address', label: 'Address' },
      { key: 'joining_date', label: 'Joining Date', type: 'date' },
      { key: 'notes', label: 'Notes', type: 'textarea' },
    ]}
    statuses={[
      { value: 'active', label: 'Active' },
      { value: 'inactive', label: 'Inactive' },
      { value: 'suspended', label: 'Suspended' },
      { value: 'terminated', label: 'Terminated' },
      { value: 'on_leave', label: 'On Leave' },
    ]}
  />
);

export const PostSitesPage = () => (
  <EntityCrudPage
    title="Post Sites" endpoint="/dispatch/post-sites" permBase="dispatch.post_sites"
    columns={[{ key: 'post_pin', label: 'Post Pin' }, { key: 'name', label: 'Name' }, { key: 'city', label: 'City' }, { key: 'required_officers', label: 'Required' }]}
    fields={[
      { key: 'post_pin', label: 'Post Pin', required: true },
      { key: 'name', label: 'Name', required: true },
      { key: 'client_id', label: 'Client', select: 'clients', required: true },
      { key: 'vendor_id', label: 'Vendor', select: 'vendors', required: true },
      { key: 'required_officers', label: 'Required Officers', type: 'number' },
      { key: 'contact_person', label: 'Contact Person' },
      { key: 'contact_number', label: 'Contact Number' },
      { key: 'address', label: 'Address' },
      { key: 'city', label: 'City' },
      { key: 'location', label: 'Location' },
      { key: 'notes', label: 'Notes', type: 'textarea' },
    ]}
  />
);
