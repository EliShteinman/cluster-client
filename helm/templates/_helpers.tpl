{{- define "cluster-client.fullname" -}}
{{- if contains .Chart.Name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{- define "cluster-client.selectorLabels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "cluster-client.labels" -}}
{{ include "cluster-client.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "cluster-client.domain" -}}
{{- required "domain is required: pass the network's values file (-f helm/networks/<network>.yaml)" .Values.domain }}
{{- end }}

{{- define "cluster-client.routeHost" -}}
{{- .Values.route.host | default (printf "%s.%s" .Values.route.name (include "cluster-client.domain" .)) }}
{{- end }}

{{- define "cluster-client.image" -}}
{{- printf "%s.%s/%s:%s" .Values.image.registry (include "cluster-client.domain" .) .Values.image.repository (.Values.image.tag | default .Chart.AppVersion) }}
{{- end }}

{{- define "cluster-client.collectorImage" -}}
{{- printf "%s.%s/%s:%s" .Values.image.registry (include "cluster-client.domain" .) .Values.collector.image.repository .Values.collector.image.tag }}
{{- end }}
