window.JobExecution = {};
JobExecution.SYNC_EXECUTE = true;

function _concurrent_execution_ui(xhr) {
  if (JobExecution.SYNC_EXECUTE) {
    // Sync execution, add waiting message
    let jobResultsSection = document.getElementById('job-results');
    jobResultsSection.innerHTML = null;
    let span = document.createElement('span');
    span.classList.add('toast');
    jobResultsSection.appendChild(span);
    span.innerHTML = 'Running job...';
    jobResultsSection.appendChild(span);
    jobResultsSection.scrollIntoView();
  }
  return
}

function _error_ui(xhr) {
  let jobResultsSection = document.getElementById('job-results');
  jobResultsSection.innerHTML = null;
  let span = document.createElement('span');
  span.innerHTML = 'Job execution error';
  jobResultsSection.appendChild(span);
  jobResultsSection.scrollIntoView();
}

function _completion_ui(xhr) {
  let jobResultsSection = document.getElementById('job-results');
  jobResultsSection.innerHTML = null;
  let responseLocation = xhr.getResponseHeader("Location");
  const jobId = responseLocation.split('/').pop();
  let h3 = document.createElement('h3');
  h3.innerHTML = jobId;
  let span = document.createElement('span');
  span.classList.add('toast');
  const creationMessage = xhr.status == 200 ? 'is available!' : 'was created!';
  span.innerHTML = 'Job <a target="_blank" href="' + responseLocation + '">' + jobId + '</a> <span class="icon-link inverse"></span> ' + creationMessage + '</span>';
  jobResultsSection.appendChild(h3);
  jobResultsSection.appendChild(span);

  let list = document.createElement('ul');
  jobResultsSection.appendChild(list);

  let responseElements = [{
    'innerHTML': 'Job status',
    'target': '_blank',
    'href': responseLocation
  }];
  if (xhr.status === 200) {
    // Synchronous execution, so the results exist too
    responseElements.push({
      'innerHTML': 'Job results',
      'target': '_blank',
      'href': responseLocation + '/results'
    });
  }

  responseElements.forEach(function(el) {
    let li = document.createElement('li');
    let a = document.createElement('a');
    Object.keys(el).forEach(function(prop) {
      a[prop] = el[prop]
    });
    let span = document.createElement('span');
    span.classList.add('icon-link');
    li.append(span);
    li.appendChild(a);
    list.appendChild(li);
  })

  jobResultsSection.appendChild(list);
  jobResultsSection.scrollIntoView();
  return
}

function submitJob(url) {
  // NOTE: need to pass base in case url is relative
  let parsedUrl = new URL(url, document.location.origin);
  if (JobExecution.SYNC_EXECUTE) {
    parsedUrl.searchParams.set('sync-execute', 'True');
  } else {
    parsedUrl.searchParams.set('async-execute', 'True');
  }
  let xhr = new XMLHttpRequest();
  xhr.onreadystatechange = function() {
    if (xhr.readyState == XMLHttpRequest.OPENED) {
      _concurrent_execution_ui(xhr);
    } else if (xhr.readyState == XMLHttpRequest.DONE && (xhr.status === 200 || xhr.status === 202)) {
      if (this.onreadystatechange) {
        xhr.onreadystatechange = null;
      }
      _completion_ui(xhr);
    } else if (xhr.readyState == XMLHttpRequest.DONE && (xhr.status >= 400)) {
      _error_ui(xhr);
    }
  }

  xhr.open('POST', parsedUrl.href, true);
  xhr.addEventListener('load', function(event) {
    console.info('Data sent and response loaded');
  });
  xhr.addEventListener('error', function(err) {
    console.error(err);
  });
  const formElem = document.querySelector('form');
  var formData = new FormData(formElem);
  var inputs = [];
  fileInputSentinel = false;
  const entries = Array.from(formData.entries());
  entries.forEach(function(entry) {
    var [id, value] = entry;
    if (typeof value === 'object' && value !== null) {
      // File
      // Note that multiple files are valid, but appear in input with duplicate
      /// IDs, e.g.
      // [{'id': 'foo', 'value': 'fileA', 'id': 'foo', 'value': 'fileB'}
      fileInputSentinel = true;
      inputs.push({id, 'value': value.name});
      formData.append(value.name, value, value.name);
    } else {
      // Collate inputs for use as a single JSON blob
      let formInputElem = document.getElementById(id) || document.getElementsByName(id)[0]
      switch(formInputElem.type) {
        case 'checkbox':
          inputs.push({
            id,
            'value': value === "on" ? true : false
          });
          break;
        case 'number':
          // NOTE in JS all numbers are float; int/float distinction is invalid
          inputs.push({
            id,
            'value': parseFloat(value)
          });
          break;
        default:
          inputs.push({id, value});
      }
    }
    formData.delete(id);
    return;
  });
  inputs = JSON.stringify({
    "inputs": inputs
  });
  if (!fileInputSentinel) {
    // Send simple JSON payload
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.send(inputs);
    return false
  }

  // Do NOT set the Content-Type header; this forces the browser to determine
  // and include the 'boundary' value for the FormData
  // Eventual value will be something like:
  // "multipart/form-data; boundary=--------------------------randomstring"

  // xhr.setRequestHeader('Content-Type', 'multipart/form-data');

  // TODO "document" is a magic term for this form data:
  //  i.e. pygeoapi looks for the "document" block in the form data and
  //  this should be reviewed, and recorded if this is considered acceptable.
  formData.append("document", inputs);
  xhr.send(formData);
  return false;
}

function submitButtonClick (input) {
  if (input.name == 'async') {
    JobExecution.SYNC_EXECUTE = false;
  } else if (input.name == 'sync') {
    JobExecution.SYNC_EXECUTE = true;
  }
};
