/**
 * Field Mappings
 * 
 * Maps resume/profile data fields to form field names.
 */

const FIELD_MAPPINGS = {
  // Name fields
  first_name: ['firstName', 'first_name', 'fname', 'given_name'],
  last_name: ['lastName', 'last_name', 'lname', 'family_name', 'surname'],
  full_name: ['fullName', 'full_name', 'name'],
  
  // Contact fields
  email: ['email', 'emailAddress', 'email_address'],
  phone: ['phone', 'phoneNumber', 'phone_number', 'telephone', 'mobile'],
  phone_stripped: ['phoneStripped', 'phone_stripped'],
  
  // Location fields
  location: ['location', 'address', 'fullAddress'],
  city: ['city'],
  state: ['state', 'region', 'province'],
  country: ['country', 'countryCode'],
  postal_code: ['postalCode', 'postal_code', 'zip', 'zipCode'],
  address: ['streetAddress', 'address1', 'addressLine1'],
  
  // Social/URL fields
  linkedin: ['linkedin', 'linkedinUrl', 'linkedin_url'],
  github: ['github', 'githubUrl', 'github_url'],
  portfolio: ['portfolio', 'portfolioUrl', 'website', 'personalWebsite'],
  
  // Professional fields
  summary: ['summary', 'professionalSummary', 'objective', 'about'],
  
  // Work authorization
  authorized_to_work: ['authorizedToWork', 'authorized_to_work', 'workAuthorization'],
  requires_sponsorship: ['requiresSponsorship', 'requires_sponsorship', 'sponsorship'],
  
  // EEO fields
  gender: ['gender', 'sex'],
  ethnicity: ['ethnicity', 'race'],
  veteran: ['veteran', 'veteranStatus'],
  disability: ['disability', 'disabilityStatus']
};

// Value transformations for dropdowns
const VALUE_TRANSFORMS = {
  countryAbbreviationsToNames: {
    'US': 'United States',
    'USA': 'United States',
    'UK': 'United Kingdom',
    'GB': 'United Kingdom',
    'CA': 'Canada',
    'AU': 'Australia',
    'DE': 'Germany',
    'FR': 'France',
    'IN': 'India',
    'CN': 'China',
    'JP': 'Japan',
    'BR': 'Brazil',
    'MX': 'Mexico',
    'ES': 'Spain',
    'IT': 'Italy',
    'NL': 'Netherlands',
    'SE': 'Sweden',
    'CH': 'Switzerland',
    'SG': 'Singapore',
    'IE': 'Ireland',
    'IL': 'Israel',
    'NZ': 'New Zealand',
    'PL': 'Poland'
  },
  
  stateAbbreviationsToNames: {
    'AL': 'Alabama',
    'AK': 'Alaska',
    'AZ': 'Arizona',
    'AR': 'Arkansas',
    'CA': 'California',
    'CO': 'Colorado',
    'CT': 'Connecticut',
    'DE': 'Delaware',
    'FL': 'Florida',
    'GA': 'Georgia',
    'HI': 'Hawaii',
    'ID': 'Idaho',
    'IL': 'Illinois',
    'IN': 'Indiana',
    'IA': 'Iowa',
    'KS': 'Kansas',
    'KY': 'Kentucky',
    'LA': 'Louisiana',
    'ME': 'Maine',
    'MD': 'Maryland',
    'MA': 'Massachusetts',
    'MI': 'Michigan',
    'MN': 'Minnesota',
    'MS': 'Mississippi',
    'MO': 'Missouri',
    'MT': 'Montana',
    'NE': 'Nebraska',
    'NV': 'Nevada',
    'NH': 'New Hampshire',
    'NJ': 'New Jersey',
    'NM': 'New Mexico',
    'NY': 'New York',
    'NC': 'North Carolina',
    'ND': 'North Dakota',
    'OH': 'Ohio',
    'OK': 'Oklahoma',
    'OR': 'Oregon',
    'PA': 'Pennsylvania',
    'RI': 'Rhode Island',
    'SC': 'South Carolina',
    'SD': 'South Dakota',
    'TN': 'Tennessee',
    'TX': 'Texas',
    'UT': 'Utah',
    'VT': 'Vermont',
    'VA': 'Virginia',
    'WA': 'Washington',
    'WV': 'West Virginia',
    'WI': 'Wisconsin',
    'WY': 'Wyoming',
    'DC': 'District of Columbia'
  },
  
  genderValues: {
    'male': 'Male',
    'm': 'Male',
    'female': 'Female',
    'f': 'Female',
    'other': 'Other',
    'prefer_not_to_say': 'Prefer not to say',
    'decline': 'Decline to self-identify'
  },
  
  booleanToYesNo: {
    true: 'Yes',
    false: 'No',
    'true': 'Yes',
    'false': 'No',
    '1': 'Yes',
    '0': 'No'
  }
};

// Degree code mappings
const DEGREE_CODES = {
  0: 'No Degree',
  1: 'High School',
  2: 'Associate',
  3: 'Bachelor',
  4: 'Master',
  5: 'Doctorate',
  6: 'Professional'
};

const DEGREE_NAMES = {
  'high school': 1,
  'ged': 1,
  'associate': 2,
  'aa': 2,
  'as': 2,
  'bachelor': 3,
  'ba': 3,
  'bs': 3,
  'bsc': 3,
  'master': 4,
  'ma': 4,
  'ms': 4,
  'msc': 4,
  'mba': 4,
  'phd': 5,
  'doctorate': 5,
  'doctoral': 5,
  'md': 6,
  'jd': 6,
  'professional': 6
};

// Make available globally for content scripts
if (typeof window !== 'undefined') {
  window.FIELD_MAPPINGS = FIELD_MAPPINGS;
  window.VALUE_TRANSFORMS = VALUE_TRANSFORMS;
  window.DEGREE_CODES = DEGREE_CODES;
  window.DEGREE_NAMES = DEGREE_NAMES;
}
