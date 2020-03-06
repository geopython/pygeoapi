function submitJob(url) {
  var elms = document.getElementsByClassName('job-form-input');
  inputs = [];
  for (var i = 0; i < elms.length; i++) {
    inputs.push({id: elms[i].name, value: elms[i].value});
  }
  var xhr = new XMLHttpRequest();
  xhr.open('POST', url, true);
  xhr.setRequestHeader('Content-type', 'application/json');
  xhr.onreadystatechange = function() {
    if (this.readyState = this.DONE && xhr.status == 201) {
      if (this.onreadystatechange) {
        xhr.onreadystatechange = null;
      }
      var jobResultsSection = document.getElementById('job-results');
      var responseLocation = xhr.getResponseHeader("Location");
      var jobId = responseLocation.split('/').pop()
      jobResultsSection.innerHTML = '<h3>Outcome for job ' + jobId + '</h3>';


      var list = document.createElement('ul');
      jobResultsSection.appendChild(list);

      responseElements = [
        {'innerHTML': 'Job status', 'target': '_blank', 'href': responseLocation},
        {'innerHTML': 'Job results', 'target': '_blank', 'href': responseLocation + '/results'}
      ]

      responseElements.forEach(function(el) {
        var li = document.createElement('li');
        var a = document.createElement('a');
        Object.keys(el).forEach(function(prop) {
          a[prop] = el[prop]
        })
        li.appendChild(a);
        list.appendChild(li);
      })

      jobResultsSection.appendChild(list);

      return false
    }
  }
  data = {"inputs": inputs}
  xhr.send(JSON.stringify(data));
  return false;
}
